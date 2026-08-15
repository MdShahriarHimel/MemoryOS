"""Authentication endpoints: register, login, refresh, logout, me."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from starlette.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import Principal, get_principal
from app.core.config import get_settings
from app.db.session import get_session
from app.schemas_auth import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenPair,
    UserOut,
)
from app.service_auth import AuthService

router = APIRouter(prefix="/v1/auth", tags=["auth"])
settings = get_settings()


def _pair(access: str, refresh: str) -> TokenPair:
    return TokenPair(
        access_token=access,
        refresh_token=refresh,
        expires_in=settings.access_token_ttl_seconds,
    )


@router.post("/register", response_model=TokenPair, status_code=201)
async def register(req: RegisterRequest, request: Request, session: AsyncSession = Depends(get_session)):
    svc = AuthService(session)
    user = await svc.register(req.email, req.password, req.organization_name)
    access = svc.issue_access_token(user)
    refresh = await svc.issue_refresh(
        user, user_agent=request.headers.get("user-agent"), ip=request.client.host if request.client else None
    )
    return _pair(access, refresh)


@router.post("/login", response_model=TokenPair)
async def login(req: LoginRequest, request: Request, session: AsyncSession = Depends(get_session)):
    svc = AuthService(session)
    user = await svc.authenticate(req.email, req.password)
    access = svc.issue_access_token(user)
    refresh = await svc.issue_refresh(
        user, user_agent=request.headers.get("user-agent"), ip=request.client.host if request.client else None
    )
    return _pair(access, refresh)


@router.post("/refresh", response_model=TokenPair)
async def refresh(req: RefreshRequest, session: AsyncSession = Depends(get_session)):
    svc = AuthService(session)
    user, new_refresh = await svc.rotate_refresh(req.refresh_token)
    access = svc.issue_access_token(user)
    return _pair(access, new_refresh)


@router.post("/logout", status_code=204, response_class=Response)
async def logout(req: RefreshRequest, session: AsyncSession = Depends(get_session)) -> Response:
    await AuthService(session).logout(req.refresh_token)
    return Response(status_code=204)


@router.get("/me", response_model=UserOut)
async def me(principal: Principal = Depends(get_principal), session: AsyncSession = Depends(get_session)):
    from sqlalchemy import select
    from app.models import User

    if principal.kind != "user":
        # API-key or anon principals still resolve to a tenant, but /me is a user route.
        return UserOut(id=principal.subject, email="", role=principal.role, organization_id=principal.tenant_id)
    user = (await session.execute(select(User).where(User.id == principal.subject))).scalar_one()
    return UserOut(id=user.id, email=user.email, role=user.role, organization_id=user.organization_id)
