"""API-key and webhook management endpoints.

API-key secrets are shown exactly once at creation. Webhook secrets likewise.
Both are stored only as hashes.
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime

from fastapi import APIRouter, Depends
from starlette.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import Principal, get_principal, require_role
from app.core.config import get_settings
from app.core.errors import NotFoundError, ValidationError
from app.security.secret_box import encrypt_secret
from app.security.url_validation import validate_webhook_url
from app.db.session import get_session
from app.models import ApiKey, Webhook, WebhookDelivery
from app.security.keys import generate_api_key
from app.security.rbac import ALL_SCOPES, Role

settings = get_settings()
router = APIRouter(prefix="/v1", tags=["developer"])


# ---- API keys -------------------------------------------------------------


class ApiKeyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    scopes: list[str] = Field(default_factory=lambda: ["memory:read"])
    environment: str = "development"


class ApiKeyOut(BaseModel):
    id: str
    name: str
    prefix: str
    scopes: list[str]
    environment: str
    revoked: bool
    last_used_at: datetime | None
    created_at: datetime


class ApiKeyCreated(ApiKeyOut):
    secret: str  # shown once


@router.get("/api-keys", response_model=list[ApiKeyOut])
async def list_api_keys(
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
):
    rows = (
        await session.execute(select(ApiKey).where(ApiKey.tenant_id == principal.tenant_id))
    ).scalars().all()
    return [ApiKeyOut(**{k: getattr(r, k) for k in ApiKeyOut.model_fields}) for r in rows]


@router.post("/api-keys", response_model=ApiKeyCreated, status_code=201)
async def create_api_key(
    req: ApiKeyCreate,
    principal: Principal = Depends(require_role(Role.admin)),
    session: AsyncSession = Depends(get_session),
):
    scopes = [s for s in req.scopes if s in ALL_SCOPES] or ["memory:read"]
    full_key, prefix, key_hash = generate_api_key()
    row = ApiKey(
        tenant_id=principal.tenant_id, name=req.name, prefix=prefix,
        key_hash=key_hash, scopes=scopes, environment=req.environment,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    out = {k: getattr(row, k) for k in ApiKeyOut.model_fields}
    return ApiKeyCreated(secret=full_key, **out)


@router.post("/api-keys/{key_id}/rotate", response_model=ApiKeyCreated)
async def rotate_api_key(
    key_id: str,
    principal: Principal = Depends(require_role(Role.admin)),
    session: AsyncSession = Depends(get_session),
):
    row = (
        await session.execute(
            select(ApiKey).where(ApiKey.id == key_id, ApiKey.tenant_id == principal.tenant_id)
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundError("API key not found.")
    full_key, prefix, key_hash = generate_api_key()
    row.prefix, row.key_hash = prefix, key_hash
    await session.commit()
    await session.refresh(row)
    out = {k: getattr(row, k) for k in ApiKeyOut.model_fields}
    return ApiKeyCreated(secret=full_key, **out)


@router.delete("/api-keys/{key_id}", status_code=204, response_class=Response)
async def revoke_api_key(
    key_id: str,
    principal: Principal = Depends(require_role(Role.admin)),
    session: AsyncSession = Depends(get_session),
) -> Response:
    row = (
        await session.execute(
            select(ApiKey).where(ApiKey.id == key_id, ApiKey.tenant_id == principal.tenant_id)
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundError("API key not found.")
    row.revoked = True
    await session.commit()
    return Response(status_code=204)


# ---- Webhooks -------------------------------------------------------------


class WebhookCreate(BaseModel):
    url: str = Field(min_length=1, max_length=500)
    events: list[str] = Field(default_factory=list)


class WebhookOut(BaseModel):
    id: str
    url: str
    events: list[str]
    status: str
    created_at: datetime


class WebhookCreated(WebhookOut):
    secret: str  # shown once


class DeliveryOut(BaseModel):
    id: str
    event: str
    status: str
    attempts: int
    response_status: int | None
    latency_ms: int | None
    created_at: datetime


@router.get("/webhooks", response_model=list[WebhookOut])
async def list_webhooks(
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
):
    rows = (
        await session.execute(select(Webhook).where(Webhook.tenant_id == principal.tenant_id))
    ).scalars().all()
    return [WebhookOut(**{k: getattr(r, k) for k in WebhookOut.model_fields}) for r in rows]


@router.post("/webhooks", response_model=WebhookCreated, status_code=201)
async def create_webhook(
    req: WebhookCreate,
    principal: Principal = Depends(require_role(Role.admin)),
    session: AsyncSession = Depends(get_session),
):
    validate_webhook_url(req.url)
    secret = f"whsec_{secrets.token_urlsafe(32)}"
    secret_hash = hashlib.sha256((secret + settings.api_key_pepper).encode()).hexdigest()
    row = Webhook(
        tenant_id=principal.tenant_id, url=req.url,
        secret_hash=secret_hash, secret_enc=encrypt_secret(secret), events=req.events,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    out = {k: getattr(row, k) for k in WebhookOut.model_fields}
    return WebhookCreated(secret=secret, **out)


@router.get("/webhooks/{webhook_id}/deliveries", response_model=list[DeliveryOut])
async def list_deliveries(
    webhook_id: str,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
):
    rows = (
        await session.execute(
            select(WebhookDelivery)
            .where(
                WebhookDelivery.webhook_id == webhook_id,
                WebhookDelivery.tenant_id == principal.tenant_id,
            )
            .order_by(WebhookDelivery.created_at.desc())
            .limit(50)
        )
    ).scalars().all()
    return [DeliveryOut(**{k: getattr(r, k) for k in DeliveryOut.model_fields}) for r in rows]


@router.delete("/webhooks/{webhook_id}", status_code=204, response_class=Response)
async def delete_webhook(
    webhook_id: str,
    principal: Principal = Depends(require_role(Role.admin)),
    session: AsyncSession = Depends(get_session),
) -> Response:
    row = (
        await session.execute(
            select(Webhook).where(Webhook.id == webhook_id, Webhook.tenant_id == principal.tenant_id)
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundError("Webhook not found.")
    await session.delete(row)
    await session.commit()
    return Response(status_code=204)
