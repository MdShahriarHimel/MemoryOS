"""Authentication service.

Implements registration, login, and refresh-token rotation with reuse detection.
The tenant_id for a single-org deployment equals the organization_id, giving a
clean tenant boundary that every downstream query enforces.
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import AuthError, ValidationError
from app.models import Organization, RefreshSession, User
from app.security import jwt as jwt_lib
from app.security.passwords import hash_password, verify_password
from app.security.rbac import Role

settings = get_settings()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _hash_token(token: str) -> str:
    return hashlib.sha256((token + settings.api_key_pepper).encode()).hexdigest()


class AuthService:
    def __init__(self, session: AsyncSession):
        self.db = session

    async def register(self, email: str, password: str, org_name: str) -> User:
        existing = (
            await self.db.execute(select(User).where(User.email == email))
        ).scalar_one_or_none()
        if existing is not None:
            raise ValidationError("Email already registered.", details={"email": email})

        org = Organization(name=org_name)
        self.db.add(org)
        await self.db.flush()

        # First user in an org is the owner.
        user = User(
            organization_id=org.id,
            email=email,
            password_hash=hash_password(password),
            role=Role.owner.value,
        )
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def authenticate(self, email: str, password: str) -> User:
        user = (
            await self.db.execute(select(User).where(User.email == email))
        ).scalar_one_or_none()
        # Constant-ish behaviour: always run a verify to reduce user enumeration.
        if user is None:
            verify_password(password, "pbkdf2_sha256$1$00$00")
            raise AuthError("Invalid credentials.")
        if not verify_password(password, user.password_hash):
            raise AuthError("Invalid credentials.")
        return user

    def issue_access_token(self, user: User) -> str:
        return jwt_lib.encode(
            {
                "sub": user.id,
                "tenant_id": user.organization_id,
                "org": user.organization_id,
                "role": user.role,
                "typ": "access",
            },
            ttl_seconds=settings.access_token_ttl_seconds,
        )

    async def issue_refresh(
        self, user: User, *, parent_id: str | None = None,
        user_agent: str | None = None, ip: str | None = None,
    ) -> str:
        raw = secrets.token_urlsafe(48)
        sess = RefreshSession(
            user_id=user.id,
            tenant_id=user.organization_id,
            token_hash=_hash_token(raw),
            parent_id=parent_id,
            user_agent=user_agent,
            ip=ip,
            expires_at=_now() + timedelta(seconds=settings.refresh_token_ttl_seconds),
        )
        self.db.add(sess)
        await self.db.commit()
        # The raw token embeds the session id so rotation can find its parent.
        return f"{sess.id}.{raw}"

    async def rotate_refresh(self, refresh_token: str) -> tuple[User, str]:
        try:
            sess_id, raw = refresh_token.split(".", 1)
        except ValueError:
            raise AuthError("Malformed refresh token.")

        sess = (
            await self.db.execute(select(RefreshSession).where(RefreshSession.id == sess_id))
        ).scalar_one_or_none()
        if sess is None or sess.token_hash != _hash_token(raw):
            raise AuthError("Invalid refresh token.")

        if sess.revoked:
            # Reuse of a rotated/revoked token → revoke the whole family.
            await self._revoke_family(sess.user_id)
            raise AuthError("Refresh token reuse detected; sessions revoked.")

        if sess.expires_at.replace(tzinfo=timezone.utc) < _now():
            raise AuthError("Refresh token expired.")

        user = (
            await self.db.execute(select(User).where(User.id == sess.user_id))
        ).scalar_one()

        sess.revoked = True  # rotate
        await self.db.commit()

        new_refresh = await self.issue_refresh(user, parent_id=sess.id)
        return user, new_refresh

    async def logout(self, refresh_token: str) -> None:
        try:
            sess_id, _ = refresh_token.split(".", 1)
        except ValueError:
            return
        sess = (
            await self.db.execute(select(RefreshSession).where(RefreshSession.id == sess_id))
        ).scalar_one_or_none()
        if sess:
            sess.revoked = True
            await self.db.commit()

    async def _revoke_family(self, user_id: str) -> None:
        rows = (
            await self.db.execute(
                select(RefreshSession).where(RefreshSession.user_id == user_id)
            )
        ).scalars().all()
        for r in rows:
            r.revoked = True
        await self.db.commit()
