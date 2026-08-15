"""Health, readiness, and dashboard/admin aggregate endpoints."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import Principal, get_tenant_id, require_role
from app.security.rbac import Role
from app.core.config import get_settings
from app.db.session import get_session
from app.infra.probes import component_status
from app.models import Agent, AnalyticsEvent, Memory, MemoryConflict, Session

router = APIRouter(tags=["system"])
settings = get_settings()


@router.get("/v1/health")
async def health() -> dict:
    return {"status": "operational", "time": datetime.now(timezone.utc).isoformat()}


@router.get("/v1/ready")
async def ready(session: AsyncSession = Depends(get_session)) -> dict:
    components: dict[str, str] = {}
    try:
        await session.execute(select(1))
        components["postgres"] = "operational"
    except Exception:
        components["postgres"] = "unavailable"

    components.update(await component_status(settings))

    required_ok = components.get("postgres") == "operational"
    optional = [components.get(k) for k in ("redis", "neo4j", "opensearch")]
    if any(v == "unavailable" for v in optional):
        overall = "degraded" if required_ok else "unavailable"
    else:
        overall = "operational" if required_ok else "unavailable"
    return {"status": overall, "components": components}


@router.get("/v1/admin/stats")
async def admin_stats(
    _principal: Principal = Depends(require_role(Role.viewer)),
    tenant_id: str = Depends(get_tenant_id),
    session: AsyncSession = Depends(get_session),
) -> dict:
    since = datetime.now(timezone.utc) - timedelta(hours=24)

    mem_count = (
        await session.execute(
            select(func.count()).select_from(Memory).where(
                Memory.tenant_id == tenant_id,
                Memory.status != "deleted",
            )
        )
    ).scalar_one()
    conflict_count = (
        await session.execute(
            select(func.count()).select_from(MemoryConflict).where(MemoryConflict.tenant_id == tenant_id)
        )
    ).scalar_one()
    session_count = (
        await session.execute(
            select(func.count()).select_from(Session).where(
                Session.tenant_id == tenant_id, Session.status == "active"
            )
        )
    ).scalar_one()
    agent_count = (
        await session.execute(
            select(func.count()).select_from(Agent).where(Agent.tenant_id == tenant_id)
        )
    ).scalar_one()
    avg_conf = (
        await session.execute(
            select(func.avg(Memory.confidence)).where(
                Memory.tenant_id == tenant_id, Memory.status != "deleted"
            )
        )
    ).scalar_one()
    retrieval_total = (
        await session.execute(
            select(func.coalesce(func.sum(AnalyticsEvent.value), 0)).where(
                AnalyticsEvent.tenant_id == tenant_id,
                AnalyticsEvent.kind == "retrieval",
                AnalyticsEvent.at >= since,
            )
        )
    ).scalar_one()
    api_requests = (
        await session.execute(
            select(func.coalesce(func.sum(AnalyticsEvent.value), 0)).where(
                AnalyticsEvent.tenant_id == tenant_id,
                AnalyticsEvent.kind.in_(["memory.created", "retrieval"]),
                AnalyticsEvent.at >= since,
            )
        )
    ).scalar_one()

    return {
        "total_memories": int(mem_count),
        "open_conflicts": int(conflict_count),
        "active_sessions": int(session_count),
        "active_agents": int(agent_count),
        "avg_confidence": float(avg_conf) if avg_conf is not None else None,
        "retrievals_24h": float(retrieval_total or 0),
        "api_requests_24h": float(api_requests or 0),
    }
