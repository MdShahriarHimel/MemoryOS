"""Usage metering API."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import Principal, get_principal, require_role
from app.db.session import get_session
from app.models import TenantQuota
from app.security.rbac import Role
from app.service_metering import get_usage_summary, get_usage_with_limits

router = APIRouter(prefix="/v1/metering", tags=["metering"])


class UsageSummaryOut(BaseModel):
    tenant_id: str
    period_days: int
    metrics: dict[str, float]
    limits: dict[str, dict[str, float]] = Field(default_factory=dict)
    generated_at: datetime


class QuotaUpdateIn(BaseModel):
    limits: dict[str, float]


class QuotaOut(BaseModel):
    tenant_id: str
    limits: dict[str, float]


@router.get("/usage", response_model=UsageSummaryOut)
async def usage_summary(
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
):
    since = datetime.now(timezone.utc) - timedelta(days=30)
    totals = await get_usage_summary(session, tenant_id=principal.tenant_id, since=since)
    limits = await get_usage_with_limits(session, tenant_id=principal.tenant_id)
    return UsageSummaryOut(
        tenant_id=principal.tenant_id,
        period_days=30,
        metrics=totals,
        limits=limits,
        generated_at=datetime.now(timezone.utc),
    )


@router.get("/quotas", response_model=QuotaOut)
async def get_quotas(
    principal: Principal = Depends(require_role(Role.admin)),
    session: AsyncSession = Depends(get_session),
):
    row = await session.get(TenantQuota, principal.tenant_id)
    return QuotaOut(tenant_id=principal.tenant_id, limits=(row.limits if row else {}))


@router.put("/quotas", response_model=QuotaOut)
async def set_quotas(
    body: QuotaUpdateIn,
    principal: Principal = Depends(require_role(Role.admin)),
    session: AsyncSession = Depends(get_session),
):
    row = await session.get(TenantQuota, principal.tenant_id)
    if row is None:
        row = TenantQuota(tenant_id=principal.tenant_id, limits=body.limits)
        session.add(row)
    else:
        row.limits = body.limits
    await session.commit()
    return QuotaOut(tenant_id=principal.tenant_id, limits=row.limits)
