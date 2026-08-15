"""Agent session listing and replay endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import Principal, require_scope
from app.db.session import get_session as get_db_session
from app.models import SessionEvent
from app.schemas import (
    SessionCreate,
    SessionEventCreate,
    SessionEventOut,
    SessionOut,
    SessionPage,
    SessionReplayResponse,
)
from app.service_sessions import (
    append_event,
    create_session,
    event_offset_seconds,
    get_session as fetch_session,
    list_events,
    list_sessions,
)

router = APIRouter(prefix="/v1/sessions", tags=["sessions"])


async def _session_out(db: AsyncSession, row) -> SessionOut:
    count = (
        await db.execute(
            select(func.count()).where(SessionEvent.session_id == row.id)
        )
    ).scalar_one()
    return SessionOut(
        id=row.id,
        tenant_id=row.tenant_id,
        agent_id=row.agent_id,
        status=row.status,
        started_at=row.started_at,
        ended_at=row.ended_at,
        event_count=int(count),
    )


@router.get("", response_model=SessionPage)
async def get_sessions(
    principal: Principal = Depends(require_scope("sessions:read")),
    db: AsyncSession = Depends(get_db_session),
    limit: int = Query(25, ge=1, le=200),
    offset: int = Query(0, ge=0),
    status: str | None = None,
) -> SessionPage:
    rows, total = await list_sessions(
        db, principal.tenant_id, limit=limit, offset=offset, status=status,
    )
    items = [await _session_out(db, r) for r in rows]
    return SessionPage(items=items, total=total, limit=limit, offset=offset)


@router.post("", response_model=SessionOut, status_code=201)
async def post_session(
    body: SessionCreate,
    principal: Principal = Depends(require_scope("memory:write")),
    db: AsyncSession = Depends(get_db_session),
) -> SessionOut:
    row = await create_session(db, principal.tenant_id, agent_id=body.agent_id)
    await db.commit()
    await db.refresh(row)
    return await _session_out(db, row)


@router.get("/{session_id}", response_model=SessionOut)
async def get_session_detail(
    session_id: str,
    principal: Principal = Depends(require_scope("sessions:read")),
    db: AsyncSession = Depends(get_db_session),
) -> SessionOut:
    row = await fetch_session(db, principal.tenant_id, session_id)
    return await _session_out(db, row)


@router.get("/{session_id}/events", response_model=SessionReplayResponse)
async def get_session_replay(
    session_id: str,
    principal: Principal = Depends(require_scope("sessions:read")),
    db: AsyncSession = Depends(get_db_session),
) -> SessionReplayResponse:
    sess, events = await list_events(db, principal.tenant_id, session_id)
    return SessionReplayResponse(
        session_id=sess.id,
        started_at=sess.started_at,
        events=[
            SessionEventOut(
                seq=e.seq,
                t=round(event_offset_seconds(sess, e), 3),
                type=e.event_type,
                detail=(e.payload or {}).get("detail", ""),
                latency_ms=e.latency_ms,
            )
            for e in events
        ],
    )


@router.post("/{session_id}/events", response_model=SessionEventOut, status_code=201)
async def post_session_event(
    session_id: str,
    body: SessionEventCreate,
    principal: Principal = Depends(require_scope("memory:write")),
    db: AsyncSession = Depends(get_db_session),
) -> SessionEventOut:
    ev = await append_event(
        db,
        principal.tenant_id,
        session_id,
        event_type=body.event_type,
        detail=body.detail,
        latency_ms=body.latency_ms,
        payload=body.payload,
    )
    sess = await fetch_session(db, principal.tenant_id, session_id)
    await db.commit()
    return SessionEventOut(
        seq=ev.seq,
        t=round(event_offset_seconds(sess, ev), 3),
        type=ev.event_type,
        detail=(ev.payload or {}).get("detail", ""),
        latency_ms=ev.latency_ms,
    )
