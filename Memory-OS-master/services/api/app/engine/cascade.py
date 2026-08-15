"""Cross-store delete cascade for GDPR and single-memory purge."""
from __future__ import annotations

from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.engine.graphstore import delete_neo4j_memory_refs
from app.engine.keyword import build_keyword_backend
from app.engine.lifecycle import LifecycleState
from app.engine.vectorstore import VectorStore
from app.models import (
    AnalyticsEvent,
    GraphEdge,
    Memory,
    MemoryConflict,
    MemoryEmbedding,
    MemoryProvenance,
    MemoryVersion,
    Session,
    SessionEvent,
)
from app.storage.object_store import build_object_store


def _record_failure(failures: list[dict], store: str, error: str) -> None:
    failures.append({"store": store, "error": error})


async def purge_memory(
    session: AsyncSession,
    *,
    tenant_id: str,
    memory_id: str,
    vector_store: VectorStore,
    hard_delete: bool = False,
) -> tuple[list[str], list[dict]]:
    """Remove a memory and related artifacts from all configured stores."""
    stores: list[str] = []
    failures: list[dict] = []
    m = (
        await session.execute(
            select(Memory).where(Memory.id == memory_id, Memory.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()
    if m is None:
        return stores, failures

    try:
        await vector_store.delete(tenant_id, memory_id)
        stores.append("pgvector")
    except Exception as exc:
        _record_failure(failures, "pgvector", str(exc))

    try:
        await build_keyword_backend().delete(tenant_id, memory_id)
        stores.append("keyword")
    except Exception as exc:
        _record_failure(failures, "keyword", str(exc))

    if await delete_neo4j_memory_refs(tenant_id, memory_id):
        stores.append("neo4j")

    edge_q = delete(GraphEdge).where(
        GraphEdge.tenant_id == tenant_id,
        GraphEdge.source_memory_id == memory_id,
    )
    result = await session.execute(edge_q)
    if result.rowcount:
        stores.append("graph")

    conflict_q = delete(MemoryConflict).where(
        MemoryConflict.tenant_id == tenant_id,
        or_(MemoryConflict.memory_a_id == memory_id, MemoryConflict.memory_b_id == memory_id),
    )
    result = await session.execute(conflict_q)
    if result.rowcount:
        stores.append("conflicts")

    # Session events referencing this memory in payload
    ev_rows = (
        await session.execute(
            select(SessionEvent).where(SessionEvent.tenant_id == tenant_id)
        )
    ).scalars().all()
    ev_ids = [e.id for e in ev_rows if e.payload.get("memory_id") == memory_id]
    if ev_ids:
        await session.execute(delete(SessionEvent).where(SessionEvent.id.in_(ev_ids)))
        stores.append("session_events")

    meta = m.meta or {}
    obj_key = meta.get("object_key") or meta.get("attachment_key")
    if obj_key:
        try:
            store = build_object_store()
            await store.delete(str(obj_key))
            stores.append("object_storage")
        except Exception as exc:
            _record_failure(failures, "object_storage", str(exc))

    if hard_delete:
        await session.execute(delete(MemoryProvenance).where(MemoryProvenance.memory_id == memory_id))
        await session.execute(delete(MemoryVersion).where(MemoryVersion.memory_id == memory_id))
        await session.execute(delete(MemoryEmbedding).where(MemoryEmbedding.memory_id == memory_id))
        await session.delete(m)
        stores.append("postgres")
    else:
        m.status = LifecycleState.DELETED.value
        stores.append("postgres")

    return list(dict.fromkeys(stores)), failures


async def purge_tenant_memories(
    session: AsyncSession,
    *,
    tenant_id: str,
    vector_store: VectorStore,
    user_id: str | None = None,
    hard_delete: bool = False,
) -> tuple[int, list[str], list[dict]]:
    """GDPR bulk delete with full cascade."""
    filters = [Memory.tenant_id == tenant_id]
    if user_id:
        filters.append(Memory.user_id == user_id)
    rows = (await session.execute(select(Memory).where(*filters))).scalars().all()
    all_stores: list[str] = []
    all_failures: list[dict] = []
    for m in rows:
        touched, failed = await purge_memory(
            session,
            tenant_id=tenant_id,
            memory_id=m.id,
            vector_store=vector_store,
            hard_delete=hard_delete,
        )
        all_stores.extend(touched)
        all_failures.extend(failed)

    if user_id:
        session_ids = {
            sid
            for sid in (
                await session.execute(
                    select(Memory.session_id).where(
                        Memory.tenant_id == tenant_id,
                        Memory.user_id == user_id,
                        Memory.session_id.isnot(None),
                    )
                )
            ).scalars().all()
            if sid
        }
        if session_ids:
            await session.execute(delete(SessionEvent).where(SessionEvent.session_id.in_(session_ids)))
            await session.execute(delete(Session).where(Session.id.in_(session_ids)))
            all_stores.append("sessions")

    if hard_delete and not user_id:
        await session.execute(delete(AnalyticsEvent).where(AnalyticsEvent.tenant_id == tenant_id))
        all_stores.append("analytics_events")

    return len(rows), list(dict.fromkeys(all_stores)), all_failures
