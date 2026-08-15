"""Analytics endpoints — real, computed series only."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import Principal, get_principal
from app.db.session import get_session
from app.engine import analytics

router = APIRouter(prefix="/v1/analytics", tags=["analytics"])


@router.get("/summary")
async def get_summary(
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
):
    return await analytics.summary(session, principal.tenant_id)


@router.get("/series")
async def get_series(
    kind: str = Query("memory.created"),
    days: int = Query(14, ge=1, le=90),
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
):
    return {
        "kind": kind,
        "days": days,
        "series": await analytics.daily_series(session, principal.tenant_id, kind, days=days),
    }
