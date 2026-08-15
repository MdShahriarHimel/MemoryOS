"""Agent session listing, event append, and replay."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError, ValidationError
from app.models import Session as AgentSession
from app.models import SessionEvent

VALID_EVENT_TYPES = frozenset({
    "request", "search", "context", "response", "memory_write",
})


async def list_sessions(
    db: AsyncSession,
    tenant_id: str,
    *,
    limit: int = 25,
    offset: int = 0,
    status: str | None = None,
) -> tuple[list[AgentSession], int]:
    filters = [AgentSession.tenant_id == tenant_id]
    if status:
        filters.append(AgentSession.status == status)
    total = (
        await db.execute(select(func.count()).select_from(AgentSession).where(*filters))
    ).scalar_one()
    rows = (
        await db.execute(
            select(AgentSession)
            .where(*filters)
            .order_by(AgentSession.started_at.desc())
            .limit(limit)
            .offset(offset)
        )
    ).scalars().all()
    return list(rows), int(total)


async def get_session(db: AsyncSession, tenant_id: str, session_id: str) -> AgentSession:
    row = (
        await db.execute(
            select(AgentSession).where(
                AgentSession.id == session_id,
                AgentSession.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundError("Session not found.")
    return row


async def create_session(
    db: AsyncSession,
    tenant_id: str,
    *,
    agent_id: str | None = None,
) -> AgentSession:
    row = AgentSession(tenant_id=tenant_id, agent_id=agent_id, status="active")
    db.add(row)
    await db.flush()
    return row


async def list_events(
    db: AsyncSession,
    tenant_id: str,
    session_id: str,
) -> tuple[AgentSession, list[SessionEvent]]:
    sess = await get_session(db, tenant_id, session_id)
    rows = (
        await db.execute(
            select(SessionEvent)
            .where(
                SessionEvent.session_id == session_id,
                SessionEvent.tenant_id == tenant_id,
            )
            .order_by(SessionEvent.seq)
        )
    ).scalars().all()
    return sess, list(rows)


def event_offset_seconds(session: AgentSession, event: SessionEvent) -> float:
    start = session.started_at
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    at = event.at
    if at.tzinfo is None:
        at = at.replace(tzinfo=timezone.utc)
    return max(0.0, (at - start).total_seconds())


async def append_event(
    db: AsyncSession,
    tenant_id: str,
    session_id: str,
    *,
    event_type: str,
    detail: str,
    latency_ms: int | None = None,
    payload: dict | None = None,
) -> SessionEvent:
    if event_type not in VALID_EVENT_TYPES:
        raise ValidationError(f"Unknown event type: {event_type}")
    await get_session(db, tenant_id, session_id)
    max_seq = (
        await db.execute(
            select(func.coalesce(func.max(SessionEvent.seq), 0)).where(
                SessionEvent.session_id == session_id
            )
        )
    ).scalar_one()
    body = {"detail": detail, **(payload or {})}
    ev = SessionEvent(
        session_id=session_id,
        tenant_id=tenant_id,
        seq=int(max_seq) + 1,
        event_type=event_type,
        payload=body,
        latency_ms=latency_ms,
    )
    db.add(ev)
    await db.flush()
    return ev


async def record_event(
    db: AsyncSession,
    tenant_id: str,
    session_id: str | None,
    *,
    event_type: str,
    detail: str,
    latency_ms: int | None = None,
) -> SessionEvent | None:
    """Best-effort event recording when a session_id is supplied on memory ops."""
    if not session_id:
        return None
    try:
        ev = await append_event(
            db,
            tenant_id,
            session_id,
            event_type=event_type,
            detail=detail,
            latency_ms=latency_ms,
        )
        await db.commit()
        return ev
    except NotFoundError:
        return None
