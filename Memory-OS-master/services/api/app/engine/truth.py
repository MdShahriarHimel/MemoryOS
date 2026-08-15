"""Temporal truth resolution — deterministic current/historical truth.

Never deletes historical memories. Resolves truth from supersession chains
and validity intervals.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from app.engine.temporal import TemporalMemory, is_valid_at, query_as_of


@dataclass
class TruthState:
    subject: str
    predicate: str
    current_value: str | None
    current_memory_id: str | None
    confidence: float
    lineage: list[str] = field(default_factory=list)
    is_current: bool = True
    as_of: datetime | None = None
    reason: str = ""


@dataclass
class CanonicalMemory:
    memory_id: str
    subject: str | None
    predicate: str | None
    object_value: str | None
    content: str
    version: int
    confidence: float
    valid_from: datetime | None
    valid_until: datetime | None
    observed_at: datetime | None
    superseded_at: datetime | None
    supersedes_id: str | None
    superseded_by_id: str | None
    created_at: datetime
    status: str = "ACTIVE"


def _to_temporal(m: CanonicalMemory) -> TemporalMemory:
    return TemporalMemory(
        memory_id=m.memory_id,
        content=m.content,
        version=m.version,
        valid_from=m.valid_from,
        valid_until=m.valid_until,
        observed_at=m.observed_at,
        superseded_at=m.superseded_at,
        supersedes_id=m.supersedes_id,
        created_at=m.created_at,
    )


def _matches(m: CanonicalMemory, subject: str, predicate: str) -> bool:
    subj = (m.subject or "user").lower()
    pred = (m.predicate or "").lower()
    return subj == subject.lower() and pred == predicate.lower()


def _build_lineage_chain(
    memories: list[CanonicalMemory], head_id: str
) -> list[str]:
    """Oldest → newest chain ending at head_id."""
    by_id = {m.memory_id: m for m in memories}
    chain: list[str] = []
    current = head_id
    visited: set[str] = set()
    while current and current not in visited:
        visited.add(current)
        m = by_id.get(current)
        if m is None:
            break
        chain.append(current)
        current = m.supersedes_id or ""
    chain.reverse()
    return chain


def resolve_current_truth(
    memories: list[CanonicalMemory],
    subject: str,
    predicate: str,
) -> TruthState:
    """Resolve the current truth for a subject+predicate pair."""
    candidates = [
        m for m in memories
        if _matches(m, subject, predicate)
        and m.status not in ("DELETED", "ARCHIVED")
        and m.superseded_at is None
        and m.superseded_by_id is None
    ]
    if not candidates:
        return TruthState(
            subject=subject, predicate=predicate,
            current_value=None, current_memory_id=None,
            confidence=0.0, reason="no_matching_memories",
        )

    # Pick highest version, then most recent observed_at
    best = max(
        candidates,
        key=lambda m: (m.version, m.observed_at or m.created_at, m.memory_id),
    )
    lineage = _build_lineage_chain(memories, best.memory_id)
    return TruthState(
        subject=subject,
        predicate=predicate,
        current_value=best.object_value or best.content,
        current_memory_id=best.memory_id,
        confidence=best.confidence,
        lineage=lineage,
        is_current=True,
        reason="current_truth_resolved",
    )


def resolve_historical_truth(
    memories: list[CanonicalMemory],
    subject: str,
    predicate: str,
    as_of: datetime,
) -> TruthState:
    """Resolve truth at a specific point in time."""
    matching = [m for m in memories if _matches(m, subject, predicate)]
    if not matching:
        return TruthState(
            subject=subject, predicate=predicate,
            current_value=None, current_memory_id=None,
            confidence=0.0, as_of=as_of, is_current=False,
            reason="no_matching_memories_at_time",
        )

    temporal = [_to_temporal(m) for m in matching]
    results = query_as_of(temporal, as_of)
    if not results:
        return TruthState(
            subject=subject, predicate=predicate,
            current_value=None, current_memory_id=None,
            confidence=0.0, as_of=as_of, is_current=False,
            reason="no_valid_memory_at_time",
        )

    best_result = results[0]
    best = next(m for m in matching if m.memory_id == best_result.memory_id)
    lineage = _build_lineage_chain(memories, best.memory_id)
    return TruthState(
        subject=subject,
        predicate=predicate,
        current_value=best.object_value or best.content,
        current_memory_id=best.memory_id,
        confidence=best.confidence,
        lineage=lineage,
        is_current=False,
        as_of=as_of,
        reason="historical_truth_resolved",
    )


def resolve_all_current_truths(memories: list[CanonicalMemory]) -> list[TruthState]:
    """Resolve current truth for every unique subject+predicate pair."""
    pairs: set[tuple[str, str]] = set()
    for m in memories:
        if m.subject and m.predicate:
            pairs.add((m.subject.lower(), m.predicate.lower()))
    return [
        resolve_current_truth(memories, subj, pred)
        for subj, pred in sorted(pairs)
    ]


def detect_temporal_overlap(a: CanonicalMemory, b: CanonicalMemory) -> bool:
    """Whether two memories have overlapping validity intervals."""
    if not _matches(a, a.subject or "user", a.predicate or ""):
        return False
    ta, tb = _to_temporal(a), _to_temporal(b)
    # Both valid at some overlapping instant?
    from datetime import timezone
    test_points = [
        a.valid_from, a.observed_at, a.created_at,
        b.valid_from, b.observed_at, b.created_at,
    ]
    for pt in test_points:
        if pt is None:
            continue
        t = pt if pt.tzinfo else pt.replace(tzinfo=timezone.utc)
        if is_valid_at(ta, t) and is_valid_at(tb, t):
            return True
    return False
