"""Analytics pipeline.

Events are appended to `analytics_events` on the write path. Aggregation queries
compute real time-bucketed series from those rows — never fabricated. When no
events exist yet, the API returns empty series and the UI shows an empty state.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AnalyticsEvent


async def record_event(session: AsyncSession, tenant_id: str, kind: str, *, value: float = 1.0, meta: dict | None = None) -> None:
    session.add(AnalyticsEvent(tenant_id=tenant_id, kind=kind, value=value, meta=meta or {}))
    # Caller controls the transaction boundary.


async def daily_series(session: AsyncSession, tenant_id: str, kind: str, *, days: int = 14) -> list[dict]:
    since = datetime.now(timezone.utc) - timedelta(days=days)
    rows = (
        await session.execute(
            select(AnalyticsEvent.at, AnalyticsEvent.value).where(
                AnalyticsEvent.tenant_id == tenant_id,
                AnalyticsEvent.kind == kind,
                AnalyticsEvent.at >= since,
            )
        )
    ).all()
    buckets: dict[str, float] = {}
    for at, value in rows:
        day = at.date().isoformat()
        buckets[day] = buckets.get(day, 0.0) + float(value)

    # Fill the full window so the chart has a continuous x-axis.
    series = []
    for i in range(days):
        d = (datetime.now(timezone.utc) - timedelta(days=days - 1 - i)).date().isoformat()
        series.append({"date": d, "value": round(buckets.get(d, 0.0), 4)})
    return series


async def summary(session: AsyncSession, tenant_id: str) -> dict:
    async def total(kind: str) -> float:
        v = (
            await session.execute(
                select(func.coalesce(func.sum(AnalyticsEvent.value), 0.0)).where(
                    AnalyticsEvent.tenant_id == tenant_id, AnalyticsEvent.kind == kind
                )
            )
        ).scalar_one()
        return float(v)

    return {
        "memory_created_total": await total("memory.created"),
        "retrieval_total": await total("retrieval"),
        "api_request_total": await total("api.request"),
    }
