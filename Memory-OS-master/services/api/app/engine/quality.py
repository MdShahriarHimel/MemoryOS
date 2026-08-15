"""Deterministic memory quality scoring.

No LLM is involved. Given the stored signals on a memory, the same inputs always
produce the same score. Weights are explicit and auditable so provenance can
explain *why* a memory scored as it did.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone

# Freshness half-life: a memory loses half its freshness contribution every N
# days since it was last observed. Deterministic exponential decay.
FRESHNESS_HALF_LIFE_DAYS = 30.0

WEIGHTS = {
    "confidence": 0.30,
    "reliability": 0.20,
    "freshness": 0.20,
    "usage": 0.15,
    "provenance": 0.10,
    "contradiction": 0.05,  # subtracted
}


@dataclass(frozen=True)
class QualitySignals:
    confidence: float          # 0..1 client-supplied belief
    reliability: float         # 0..1 source reliability
    observed_at: datetime | None
    access_count: int          # times retrieved
    has_provenance: bool
    conflict_count: int        # open conflicts touching this memory


@dataclass(frozen=True)
class QualityBreakdown:
    score: float
    freshness: float
    usage: float
    provenance: float
    contradiction_penalty: float
    components: dict[str, float]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def freshness_score(observed_at: datetime | None) -> float:
    if observed_at is None:
        return 0.5  # unknown recency → neutral
    if observed_at.tzinfo is None:
        observed_at = observed_at.replace(tzinfo=timezone.utc)
    age_days = max(0.0, (_now() - observed_at).total_seconds() / 86400.0)
    return 0.5 ** (age_days / FRESHNESS_HALF_LIFE_DAYS)


def usage_score(access_count: int) -> float:
    # Diminishing returns; saturates around ~50 accesses. Deterministic.
    return 1.0 - math.exp(-access_count / 12.0)


def compute_quality(signals: QualitySignals) -> QualityBreakdown:
    fresh = freshness_score(signals.observed_at)
    usage = usage_score(signals.access_count)
    prov = 1.0 if signals.has_provenance else 0.0
    # Contradiction penalty saturates: one conflict hurts, five don't hurt 5x.
    contra = 1.0 - math.exp(-signals.conflict_count / 2.0)

    components = {
        "confidence": _clamp(signals.confidence) * WEIGHTS["confidence"],
        "reliability": _clamp(signals.reliability) * WEIGHTS["reliability"],
        "freshness": fresh * WEIGHTS["freshness"],
        "usage": usage * WEIGHTS["usage"],
        "provenance": prov * WEIGHTS["provenance"],
    }
    penalty = contra * WEIGHTS["contradiction"]
    score = _clamp(sum(components.values()) - penalty)

    return QualityBreakdown(
        score=round(score, 4),
        freshness=round(fresh, 4),
        usage=round(usage, 4),
        provenance=prov,
        contradiction_penalty=round(penalty, 4),
        components={k: round(v, 4) for k, v in components.items()},
    )


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))
