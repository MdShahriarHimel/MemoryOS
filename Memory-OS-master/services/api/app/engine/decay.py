"""Deterministic memory decay scoring.

Decay influences ranking and archival decisions — never auto-deletes memories.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass
class DecayPolicy:
    """Per-tenant decay configuration."""
    base_half_life_days: float = 90.0
    importance_weight: float = 0.4
    confidence_weight: float = 0.2
    access_weight: float = 0.3
    type_weight: float = 0.1
    superseded_penalty: float = 0.3
    contradiction_penalty: float = 0.5
    min_score: float = 0.05


# Memory types with slow decay (retain longer)
_SLOW_DECAY_TYPES = frozenset({
    "fact", "preference", "profile", "semantic", "relationship",
})
_FAST_DECAY_TYPES = frozenset({"event", "observation", "episodic"})


@dataclass
class DecaySignals:
    importance: float
    confidence: float
    access_count: int
    memory_type: str
    age_days: float
    last_accessed_days: float | None
    is_superseded: bool
    contradiction_status: str
    explicitly_confirmed: bool = False


def compute_decay_score(signals: DecaySignals, policy: DecayPolicy | None = None) -> float:
    """Return decay score 0..1 where 1 = fully fresh, 0 = fully decayed."""
    p = policy or DecayPolicy()

    if signals.explicitly_confirmed:
        return 1.0

    # Age decay (exponential)
    half_life = p.base_half_life_days
    if signals.memory_type in _SLOW_DECAY_TYPES:
        half_life *= 2.0
    elif signals.memory_type in _FAST_DECAY_TYPES:
        half_life *= 0.5

    age_factor = 0.5 ** (signals.age_days / max(half_life, 1.0))

    # Boost from importance, confidence, access
    importance_boost = signals.importance * p.importance_weight
    confidence_boost = signals.confidence * p.confidence_weight
    access_boost = min(signals.access_count / 10.0, 1.0) * p.access_weight

    type_boost = p.type_weight if signals.memory_type in _SLOW_DECAY_TYPES else 0.0

    score = age_factor + importance_boost + confidence_boost + access_boost + type_boost

    if signals.is_superseded:
        score *= (1.0 - p.superseded_penalty)

    if signals.contradiction_status not in ("none", ""):
        score *= (1.0 - p.contradiction_penalty)

    if signals.last_accessed_days is not None and signals.last_accessed_days < 7:
        score = min(1.0, score + 0.1)

    return max(p.min_score, min(1.0, score))


def decay_signals_from_memory(
    *,
    importance: float,
    confidence: float,
    access_count: int,
    memory_type: str,
    created_at: datetime,
    last_accessed_at: datetime | None,
    superseded_at: datetime | None,
    contradiction_status: str,
    metadata: dict | None = None,
    now: datetime | None = None,
) -> DecaySignals:
    now = now or datetime.now(timezone.utc)
    if created_at is None:
        created_at = now
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    age_days = (now - created_at).total_seconds() / 86400.0
    last_accessed_days = None
    if last_accessed_at:
        la = last_accessed_at if last_accessed_at.tzinfo else last_accessed_at.replace(tzinfo=timezone.utc)
        last_accessed_days = (now - la).total_seconds() / 86400.0

    meta = metadata or {}
    return DecaySignals(
        importance=importance,
        confidence=confidence,
        access_count=access_count,
        memory_type=memory_type,
        age_days=age_days,
        last_accessed_days=last_accessed_days,
        is_superseded=superseded_at is not None,
        contradiction_status=contradiction_status,
        explicitly_confirmed=bool(meta.get("explicitly_confirmed")),
    )
