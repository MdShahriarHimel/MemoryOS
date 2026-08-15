"""Operations endpoints: deduplication, conflicts, temporal queries, reflection."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import Principal, get_principal, require_role
from app.db.session import get_session
from app.engine.conflicts import MemoryConflictInput, analyze_conflicts
from app.engine.consolidation import MemorySnapshot, run_reflection
from app.service_consolidation import execute_actions
from app.engine.deduplication import MemoryRecord, find_duplicates
from app.engine.entity_resolution import EntityCandidate, resolve_entities
from app.engine.temporal import TemporalMemory, query_as_of, build_lineage
from app.models import Memory, MemoryEmbedding
from app.security.rbac import Role

router = APIRouter(prefix="/v1/operations", tags=["operations"])


class DuplicateClusterOut(BaseModel):
    canonical_id: str
    duplicate_ids: list[str]
    reason: str
    score: float


class ConflictOut(BaseModel):
    memory_a: str
    memory_b: str
    reason: str
    severity: float
    signals: list[str]


class ReflectionOut(BaseModel):
    scanned: int
    summary: dict[str, int]
    actions: list[dict]


class ReflectionExecuteOut(BaseModel):
    scanned: int
    summary: dict[str, int]
    dry_run: bool
    planned: list[dict]
    results: list[dict]


class ReflectionExecuteRequest(BaseModel):
    stale_days: int = Field(default=90, ge=1, le=365)
    dry_run: bool = Field(default=True)
    max_actions: int = Field(default=100, ge=1, le=500)
    action_types: list[str] | None = Field(
        default=None,
        description="Optional filter: merge, archive, review_conflict, fix_provenance",
    )


class TemporalQueryOut(BaseModel):
    memory_id: str
    content: str
    version: int
    as_of: datetime
    valid: bool
    reason: str


class EntityMergeOut(BaseModel):
    canonical_key: str
    canonical_label: str
    merged_keys: list[str]
    reason: str
    score: float


class EntityResolutionOut(BaseModel):
    merge_groups: list[EntityMergeOut]
    resolved_count: int


@router.get("/entity-resolution", response_model=EntityResolutionOut)
async def scan_entity_resolution(
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
):
    """Find entity label clusters that likely refer to the same entity."""
    nodes = (
        await session.execute(
            select(Memory).where(
                Memory.tenant_id == principal.tenant_id,
                Memory.subject.isnot(None),
            )
        )
    ).scalars().all()
    candidates = [
        EntityCandidate(
            key=m.subject or "",
            label=m.subject or m.content[:80],
            entity_type="Subject",
            memory_ids=[m.id],
            confidence=m.confidence,
        )
        for m in nodes
        if m.subject
    ]
    groups, resolved = resolve_entities(candidates)
    return EntityResolutionOut(
        merge_groups=[
            EntityMergeOut(
                canonical_key=g.canonical_key,
                canonical_label=g.canonical_label,
                merged_keys=g.merged_keys,
                reason=g.reason,
                score=g.score,
            )
            for g in groups
        ],
        resolved_count=len(resolved),
    )


@router.get("/deduplication", response_model=list[DuplicateClusterOut])
async def scan_duplicates(
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
    jaccard_threshold: float = Query(0.85, ge=0, le=1),
):
    rows = (
        await session.execute(select(Memory).where(Memory.tenant_id == principal.tenant_id))
    ).scalars().all()
    embeds = {
        e.memory_id: e.embedding
        for e in (
            await session.execute(
                select(MemoryEmbedding).where(MemoryEmbedding.tenant_id == principal.tenant_id)
            )
        ).scalars().all()
    }
    clusters = find_duplicates(
        [MemoryRecord(m.id, m.content, embeds.get(m.id)) for m in rows],
        jaccard_threshold=jaccard_threshold,
    )
    return [
        DuplicateClusterOut(
            canonical_id=c.canonical_id,
            duplicate_ids=c.duplicate_ids,
            reason=c.reason,
            score=c.score,
        )
        for c in clusters
    ]


@router.get("/conflicts", response_model=list[ConflictOut])
async def scan_conflicts(
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
):
    rows = (
        await session.execute(select(Memory).where(Memory.tenant_id == principal.tenant_id))
    ).scalars().all()
    reports = analyze_conflicts(
        [
            MemoryConflictInput(m.id, m.content, m.valid_from, m.valid_until)
            for m in rows
        ]
    )
    return [
        ConflictOut(
            memory_a=r.memory_a,
            memory_b=r.memory_b,
            reason=r.reason,
            severity=r.severity,
            signals=r.signals,
        )
        for r in reports
    ]


@router.get("/temporal/as-of", response_model=list[TemporalQueryOut])
async def temporal_as_of(
    as_of: datetime,
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
):
    rows = (
        await session.execute(select(Memory).where(Memory.tenant_id == principal.tenant_id))
    ).scalars().all()
    temporal = [
        TemporalMemory(
            m.id, m.content, m.version, m.valid_from, m.valid_until,
            m.observed_at, m.superseded_at, m.supersedes_memory_id, m.created_at,
        )
        for m in rows
    ]
    results = query_as_of(temporal, as_of)
    return [
        TemporalQueryOut(
            memory_id=r.memory_id,
            content=r.content,
            version=r.version,
            as_of=r.as_of,
            valid=r.valid,
            reason=r.reason,
        )
        for r in results
    ]


@router.get("/temporal/lineage")
async def temporal_lineage(
    principal: Principal = Depends(get_principal),
    session: AsyncSession = Depends(get_session),
):
    rows = (
        await session.execute(select(Memory).where(Memory.tenant_id == principal.tenant_id))
    ).scalars().all()
    temporal = [
        TemporalMemory(
            m.id, m.content, m.version, m.valid_from, m.valid_until,
            m.observed_at, m.superseded_at, m.supersedes_memory_id, m.created_at,
        )
        for m in rows
    ]
    return {"chains": build_lineage(temporal)}


@router.post("/reflection", response_model=ReflectionOut)
async def trigger_reflection(
    principal: Principal = Depends(require_role(Role.admin)),
    session: AsyncSession = Depends(get_session),
    stale_days: int = Query(90, ge=1, le=365),
):
    report = run_reflection(
        await _load_snapshots(session, principal.tenant_id),
        stale_days=stale_days,
    )
    return ReflectionOut(
        scanned=report.scanned,
        summary=report.summary,
        actions=[
            {"action": a.action, "memory_ids": a.memory_ids, "reason": a.reason, "priority": a.priority}
            for a in report.actions
        ],
    )


async def _load_snapshots(session: AsyncSession, tenant_id: str) -> list[MemorySnapshot]:
    rows = (
        await session.execute(select(Memory).where(Memory.tenant_id == tenant_id))
    ).scalars().all()
    embeds = {
        e.memory_id: e.embedding
        for e in (
            await session.execute(
                select(MemoryEmbedding).where(MemoryEmbedding.tenant_id == tenant_id)
            )
        ).scalars().all()
    }
    return [
        MemorySnapshot(
            m.id, m.content, m.status, m.source, m.created_at, m.last_accessed_at,
            m.valid_from, m.valid_until, embeds.get(m.id),
        )
        for m in rows
    ]


@router.post("/reflection/execute", response_model=ReflectionExecuteOut)
async def execute_reflection(
    body: ReflectionExecuteRequest,
    principal: Principal = Depends(require_role(Role.admin)),
    session: AsyncSession = Depends(get_session),
):
    snapshots = await _load_snapshots(session, principal.tenant_id)
    report = run_reflection(snapshots, stale_days=body.stale_days)
    action_filter = set(body.action_types) if body.action_types else None
    results = await execute_actions(
        session,
        principal.tenant_id,
        report.actions,
        dry_run=body.dry_run,
        max_actions=body.max_actions,
        action_filter=action_filter,
    )

    if not body.dry_run:
        try:
            from app.telemetry.metrics import MEMORY_CONSOLIDATED, _AVAILABLE
            if _AVAILABLE:
                applied = sum(1 for r in results if r.result == "applied")
                if applied:
                    MEMORY_CONSOLIDATED.labels(principal.tenant_id).inc(applied)
        except Exception:
            pass

    planned = [
        {"action": a.action, "memory_ids": a.memory_ids, "reason": a.reason, "priority": a.priority}
        for a in report.actions[: body.max_actions]
    ]
    return ReflectionExecuteOut(
        scanned=report.scanned,
        summary=report.summary,
        dry_run=body.dry_run,
        planned=planned,
        results=[
            {
                "action": r.action,
                "memory_ids": r.memory_ids,
                "result": r.result,
                "detail": r.detail,
                "reason": r.reason,
            }
            for r in results
        ],
    )
