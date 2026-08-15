"""Deterministic memory lifecycle.

States: NEW ACTIVE AGING STALE SUPERSEDED CONFLICTED ARCHIVED DELETED

Transitions are computed from stored signals only. No LLM decisions.
The engine never *silently* overwrites; SUPERSEDED/CONFLICTED preserve history.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

AGING_DAYS = 30
STALE_DAYS = 90


class LifecycleState(str, Enum):
    NEW = "NEW"
    ACTIVE = "ACTIVE"
    AGING = "AGING"
    STALE = "STALE"
    SUPERSEDED = "SUPERSEDED"
    CONFLICTED = "CONFLICTED"
    ARCHIVED = "ARCHIVED"
    DELETED = "DELETED"


# Terminal / manually-controlled states are never auto-changed by the engine.
FROZEN = {LifecycleState.SUPERSEDED, LifecycleState.ARCHIVED, LifecycleState.DELETED}


def derive_state(
    *,
    current: LifecycleState,
    created_at: datetime,
    last_accessed_at: datetime | None,
    superseded_at: datetime | None,
    open_conflicts: int,
) -> LifecycleState:
    if current in FROZEN:
        return current
    if superseded_at is not None:
        return LifecycleState.SUPERSEDED
    if open_conflicts > 0:
        return LifecycleState.CONFLICTED

    reference = last_accessed_at or created_at
    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=timezone.utc)
    age_days = (datetime.now(timezone.utc) - reference).total_seconds() / 86400.0

    if age_days >= STALE_DAYS:
        return LifecycleState.STALE
    if age_days >= AGING_DAYS:
        return LifecycleState.AGING
    if current == LifecycleState.NEW:
        return LifecycleState.ACTIVE
    return LifecycleState.ACTIVE
