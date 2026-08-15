"""Usage metering service."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import QuotaExceededError
from app.models import TenantQuota, UsageMeter

settings = get_settings()

_DEFAULT_LIMITS = {
    "memory.write": lambda: settings.default_monthly_memory_writes,
    "memory.search": lambda: settings.default_monthly_memory_searches,
    "context.build": lambda: settings.default_monthly_context_builds,
    "api.request": lambda: settings.default_monthly_memory_searches * 2,
}


def _month_start(now: datetime | None = None) -> datetime:
    now = now or datetime.now(timezone.utc)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _hour_window(now: datetime | None = None) -> tuple[datetime, datetime]:
    now = now or datetime.now(timezone.utc)
    start = now.replace(minute=0, second=0, microsecond=0)
    end = start + timedelta(hours=1)
    return start, end


async def _resolve_limit(session: AsyncSession, tenant_id: str, metric: str) -> float:
    row = (
        await session.execute(select(TenantQuota).where(TenantQuota.tenant_id == tenant_id))
    ).scalar_one_or_none()
    if row and metric in (row.limits or {}):
        return float(row.limits[metric])
    factory = _DEFAULT_LIMITS.get(metric)
    return float(factory()) if factory else float("inf")


async def get_monthly_usage(session: AsyncSession, tenant_id: str, metric: str) -> float:
    since = _month_start()
    v = (
        await session.execute(
            select(func.coalesce(func.sum(UsageMeter.quantity), 0.0)).where(
                UsageMeter.tenant_id == tenant_id,
                UsageMeter.metric == metric,
                UsageMeter.window_start >= since,
            )
        )
    ).scalar_one()
    return float(v)


async def enforce_quota(session: AsyncSession, *, tenant_id: str, metric: str, delta: float = 1.0) -> None:
    if not settings.quota_enforcement_enabled:
        return
    limit = await _resolve_limit(session, tenant_id, metric)
    if limit == float("inf"):
        return
    used = await get_monthly_usage(session, tenant_id, metric)
    if used + delta > limit:
        raise QuotaExceededError(
            "Monthly quota exceeded.",
            details={"metric": metric, "limit": limit, "used": used},
        )


async def increment_usage(
    session: AsyncSession,
    *,
    tenant_id: str,
    metric: str,
    quantity: float = 1.0,
    now: datetime | None = None,
) -> UsageMeter:
    start, end = _hour_window(now)
    row = (
        await session.execute(
            select(UsageMeter).where(
                UsageMeter.tenant_id == tenant_id,
                UsageMeter.metric == metric,
                UsageMeter.window_start == start,
            )
        )
    ).scalar_one_or_none()

    if row is None:
        row = UsageMeter(
            tenant_id=tenant_id,
            metric=metric,
            quantity=quantity,
            window_start=start,
            window_end=end,
        )
        session.add(row)
    else:
        row.quantity += quantity
    return row


async def get_usage_summary(
    session: AsyncSession,
    *,
    tenant_id: str,
    since: datetime | None = None,
) -> dict[str, float]:
    since = since or (datetime.now(timezone.utc) - timedelta(days=30))
    rows = (
        await session.execute(
            select(UsageMeter).where(
                UsageMeter.tenant_id == tenant_id,
                UsageMeter.window_start >= since,
            )
        )
    ).scalars().all()

    totals: dict[str, float] = {}
    for r in rows:
        totals[r.metric] = totals.get(r.metric, 0.0) + r.quantity
    return totals


async def get_usage_with_limits(session: AsyncSession, *, tenant_id: str) -> dict[str, dict[str, float]]:
    since = _month_start()
    totals = await get_usage_summary(session, tenant_id=tenant_id, since=since)
    out: dict[str, dict[str, float]] = {}
    metrics = set(totals) | set(_DEFAULT_LIMITS)
    for metric in metrics:
        used = totals.get(metric, 0.0)
        limit = await _resolve_limit(session, tenant_id, metric)
        remaining = max(limit - used, 0.0) if limit != float("inf") else float("inf")
        out[metric] = {"used": used, "limit": limit, "remaining": remaining}
    return out
