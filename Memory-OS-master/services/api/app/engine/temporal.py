"""Deep temporal versioning for memories.

Supports:
  - Point-in-time queries (as-of)
  - Version lineage (supersedes / superseded_by chains)
  - Validity interval intersection checks
  - Bi-temporal fields: valid_time + transaction_time (created_at)

All operations are deterministic and tenant-scoped at the service layer.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


@dataclass
class TemporalMemory:
    memory_id: str
    content: str
    version: int
    valid_from: datetime | None
    valid_until: datetime | None
    observed_at: datetime | None
    superseded_at: datetime | None
    supersedes_id: str | None
    created_at: datetime


@dataclass
class TemporalQueryResult:
    memory_id: str
    content: str
    version: int
    as_of: datetime
    valid: bool
    reason: str


def is_valid_at(m: TemporalMemory, as_of: datetime) -> bool:
    """Whether memory was valid at a given instant."""
    t = _aware(as_of)
    vf = _aware(m.valid_from) or _aware(m.observed_at) or _aware(m.created_at)
    vu = _aware(m.valid_until)
    sa = _aware(m.superseded_at)

    if sa and t >= sa:
        return False
    if vf and t < vf:
        return False
    if vu and t > vu:
        return False
    return True


def query_as_of(memories: list[TemporalMemory], as_of: datetime) -> list[TemporalQueryResult]:
    """Return memories valid at `as_of`, newest version wins per lineage root."""
    valid = [m for m in memories if is_valid_at(m, as_of)]
    # Group by supersedes chain root — pick highest version
    by_root: dict[str, TemporalMemory] = {}
    for m in valid:
        root = m.supersedes_id or m.memory_id
        prev = by_root.get(root)
        if prev is None or m.version > prev.version:
            by_root[root] = m

    results: list[TemporalQueryResult] = []
    for m in by_root.values():
        results.append(
            TemporalQueryResult(
                memory_id=m.memory_id,
                content=m.content,
                version=m.version,
                as_of=as_of,
                valid=True,
                reason="valid_at_as_of",
            )
        )
    results.sort(key=lambda r: (-r.version, r.memory_id))
    return results


def build_lineage(memories: list[TemporalMemory]) -> list[list[str]]:
    """Return chains ordered oldest → newest by supersedes links."""
    by_id = {m.memory_id: m for m in memories}
    child_of: dict[str, str | None] = {m.memory_id: m.supersedes_id for m in memories}
    roots = [m.memory_id for m in memories if m.supersedes_id is None or m.supersedes_id not in by_id]

    chains: list[list[str]] = []
    for root in sorted(roots):
        chain = [root]
        current = root
        while True:
            nxt = [m.memory_id for m in memories if m.supersedes_id == current]
            if not nxt:
                break
            nxt_id = sorted(nxt)[0]
            chain.append(nxt_id)
            current = nxt_id
        if len(chain) > 1:
            chains.append(chain)
    return chains


def next_version(current: int, *, minor: bool = False) -> int:
    return current + 1 if not minor else current
