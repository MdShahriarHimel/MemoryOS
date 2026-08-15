"""Request dependencies: authentication, tenant resolution, RBAC, scopes.

Two auth methods are accepted:
  1. Bearer JWT  (dashboard users)          -> Authorization: Bearer <access_jwt>
  2. API key     (external agents / SDK/MCP) -> Authorization: Bearer mos_<...>

Tenant isolation flows from whichever principal is resolved. For frictionless
local exploration an X-Tenant-ID header (or a demo default) is accepted ONLY when
no Authorization header is present and MEMORY_OS_ALLOW_ANON is enabled.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone

from fastapi import Depends, Header, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import AuthError, ForbiddenError
from app.db.rls import set_rls_tenant
from app.db.session import SessionFactory, get_session
from app.models import ApiKey
from app.security import jwt as jwt_lib
from app.security.keys import hash_api_key, verify_api_key
from app.security.rbac import DEFAULT_SCOPES_FOR_ROLE, Role, effective_role, role_satisfies, scope_satisfies
from app.service import MemoryService, build_vector_store

_vector_store = build_vector_store(SessionFactory)

DEMO_TENANT = "demo-tenant"


def _allow_anon() -> bool:
    raw = os.environ.get("MEMORY_OS_ALLOW_ANON")
    if raw is not None:
        return raw.lower() == "true"
    return get_settings().memory_os_allow_anon


@dataclass
class Principal:
    tenant_id: str
    subject: str
    kind: str            # "user" | "api_key" | "anon"
    role: str
    scopes: list[str]


async def get_principal(
    request: Request,
    session: AsyncSession = Depends(get_session),
    authorization: str | None = Header(default=None),
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-ID"),
) -> Principal:
    principal: Principal
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()

        if token.startswith("mos_"):
            key_hash = hash_api_key(token)
            row = (
                await session.execute(select(ApiKey).where(ApiKey.key_hash == key_hash))
            ).scalar_one_or_none()
            if row is None or row.revoked or not verify_api_key(token, row.key_hash):
                raise AuthError("Invalid API key.")
            row.last_used_at = datetime.now(timezone.utc)
            await session.commit()
            principal = Principal(
                tenant_id=row.tenant_id, subject=row.id, kind="api_key",
                role=Role.developer.value, scopes=list(row.scopes or []),
            )
        else:
            payload = jwt_lib.decode(token)
            role = payload.get("role", Role.viewer.value)
            principal = Principal(
                tenant_id=payload["tenant_id"], subject=payload["sub"], kind="user",
                role=role, scopes=list(DEFAULT_SCOPES_FOR_ROLE.get(Role(role), set())),
            )
    elif _allow_anon():
        principal = Principal(
            tenant_id=x_tenant_id or DEMO_TENANT, subject="anon", kind="anon",
            role=Role.owner.value, scopes=["admin"],
        )
    else:
        raise AuthError("Authentication required.")

    await set_rls_tenant(session, principal.tenant_id)
    request.state.tenant_id = principal.tenant_id
    request.state.actor = principal.subject
    return principal


def require_role(minimum: Role):
    async def _dep(principal: Principal = Depends(get_principal)) -> Principal:
        role = effective_role(principal.role, kind=principal.kind, scopes=principal.scopes)
        if not role_satisfies(role, minimum):
            raise ForbiddenError(
                "Insufficient role.",
                details={"required": minimum.value, "actual": principal.role, "effective": role},
            )
        return principal
    return _dep


def require_scope(scope: str):
    async def _dep(principal: Principal = Depends(get_principal)) -> Principal:
        if principal.kind == "api_key" and not scope_satisfies(principal.scopes, scope):
            raise ForbiddenError("Missing scope.", details={"required": scope})
        return principal
    return _dep


def require_memory_read():
    """JWT users need viewer+; API keys need memory:read (or admin)."""

    async def _dep(principal: Principal = Depends(get_principal)) -> Principal:
        if principal.kind == "api_key":
            if not scope_satisfies(principal.scopes, "memory:read"):
                raise ForbiddenError("Missing scope.", details={"required": "memory:read"})
            return principal
        role = effective_role(principal.role, kind=principal.kind, scopes=principal.scopes)
        if not role_satisfies(role, Role.viewer):
            raise ForbiddenError(
                "Insufficient role for read access.",
                details={"required": Role.viewer.value, "actual": principal.role},
            )
        return principal

    return _dep


def require_memory_write():
    """JWT users need developer+; API keys need memory:write (or admin)."""

    async def _dep(principal: Principal = Depends(get_principal)) -> Principal:
        if principal.kind == "api_key":
            if not scope_satisfies(principal.scopes, "memory:write"):
                raise ForbiddenError("Missing scope.", details={"required": "memory:write"})
            return principal
        role = effective_role(principal.role, kind=principal.kind, scopes=principal.scopes)
        if not role_satisfies(role, Role.developer):
            raise ForbiddenError(
                "Insufficient role for write access.",
                details={"required": Role.developer.value, "actual": principal.role},
            )
        return principal

    return _dep


def require_quota(metric: str):
    async def _dep(
        principal: Principal = Depends(get_principal),
        session: AsyncSession = Depends(get_session),
    ) -> Principal:
        from app.service_metering import enforce_quota

        await enforce_quota(session, tenant_id=principal.tenant_id, metric=metric)
        return principal

    return _dep


async def get_tenant_id(principal: Principal = Depends(get_principal)) -> str:
    return principal.tenant_id


async def get_memory_service(
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
) -> MemoryService:
    return MemoryService(session=session, vector_store=_vector_store, tenant_id=principal.tenant_id)


async def get_memory_service_read(
    principal: Principal = Depends(require_memory_read()),
    session: AsyncSession = Depends(get_session),
) -> MemoryService:
    return MemoryService(session=session, vector_store=_vector_store, tenant_id=principal.tenant_id)


async def get_memory_service_write(
    principal: Principal = Depends(require_memory_write()),
    session: AsyncSession = Depends(get_session),
) -> MemoryService:
    return MemoryService(session=session, vector_store=_vector_store, tenant_id=principal.tenant_id)
