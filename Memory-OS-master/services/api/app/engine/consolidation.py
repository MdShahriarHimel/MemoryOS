"""Memory consolidation and advanced reflection.

Deterministic health scan that produces actionable consolidation plans:
  - Duplicate merge candidates (from deduplication engine)
  - Stale memory archival candidates
  - Conflict triage queue
  - Provenance gap remediation

Reflection returns a plan for operators to review. Apply it explicitly via
POST /v1/operations/reflection/execute — nothing mutates automatically here.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from app.engine.conflicts import MemoryConflictInput, analyze_conflicts
from app.engine.deduplication import MemoryRecord, find_duplicates
from app.engine.lifecycle import LifecycleState


@dataclass
class ConsolidationAction:
    action: str  # merge | archive | review_conflict | fix_provenance
    memory_ids: list[str]
    reason: str
    priority: float  # 0..1


@dataclass
class ReflectionReport:
    scanned: int
    actions: list[ConsolidationAction] = field(default_factory=list)
    summary: dict[str, int] = field(default_factory=dict)


@dataclass
class MemorySnapshot:
    memory_id: str
    content: str
    status: str
    source: str | None
    created_at: datetime
    last_accessed_at: datetime | None
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    embedding: list[float] | None = None


def run_reflection(
    memories: list[MemorySnapshot],
    *,
    stale_days: int = 90,
    now: datetime | None = None,
) -> ReflectionReport:
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=stale_days)

    actions: list[ConsolidationAction] = []

    # Duplicates
    dupes = find_duplicates(
        [MemoryRecord(m.memory_id, m.content, m.embedding) for m in memories]
    )
    for cluster in dupes:
        actions.append(
            ConsolidationAction(
                "merge",
                [cluster.canonical_id, *cluster.duplicate_ids],
                cluster.reason,
                cluster.score,
            )
        )

    # Stale archival
    for m in memories:
        if m.status in (LifecycleState.STALE.value, LifecycleState.AGING.value):
            actions.append(
                ConsolidationAction("archive", [m.memory_id], "lifecycle_stale", 0.5)
            )
        elif m.last_accessed_at and m.last_accessed_at < cutoff:
            actions.append(
                ConsolidationAction("archive", [m.memory_id], f"inactive_{stale_days}d", 0.4)
            )

    # Provenance gaps
    for m in memories:
        if m.source is None:
            actions.append(
                ConsolidationAction("fix_provenance", [m.memory_id], "missing_source", 0.6)
            )

    # Conflicts
    conflicts = analyze_conflicts(
        [
            MemoryConflictInput(m.memory_id, m.content, m.valid_from, m.valid_until)
            for m in memories
        ]
    )
    for c in conflicts:
        actions.append(
            ConsolidationAction(
                "review_conflict",
                [c.memory_a, c.memory_b],
                c.reason,
                c.severity,
            )
        )

    actions.sort(key=lambda a: (-a.priority, a.action))

    summary = {
        "merge": sum(1 for a in actions if a.action == "merge"),
        "archive": sum(1 for a in actions if a.action == "archive"),
        "review_conflict": sum(1 for a in actions if a.action == "review_conflict"),
        "fix_provenance": sum(1 for a in actions if a.action == "fix_provenance"),
    }

    return ReflectionReport(scanned=len(memories), actions=actions, summary=summary)
