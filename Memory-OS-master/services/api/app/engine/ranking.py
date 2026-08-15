"""Deterministic hybrid ranking.

Fuses candidates from vector, keyword, and graph channels using Reciprocal Rank
Fusion (RRF) plus quality and importance boosts. Fully deterministic — identical
candidate sets produce identical orderings. No learned reranker, no LLM.
"""
from __future__ import annotations

from dataclasses import dataclass, field

RRF_K = 60  # standard RRF constant

CHANNEL_WEIGHTS = {
    "vector": 1.0,
    "keyword": 0.8,
    "graph": 0.5,
}

QUALITY_BOOST = 0.25
IMPORTANCE_BOOST = 0.15


@dataclass
class Candidate:
    memory_id: str
    channels: dict[str, int] = field(default_factory=dict)  # channel -> rank (0-based)
    quality: float = 0.0
    importance: float = 0.0
    raw_scores: dict[str, float] = field(default_factory=dict)


@dataclass
class RankedResult:
    memory_id: str
    score: float
    channels: list[str]
    explanation: dict[str, float]


def fuse_and_rank(candidates: list[Candidate], *, top_k: int) -> list[RankedResult]:
    results: list[RankedResult] = []
    for c in candidates:
        rrf = 0.0
        for channel, rank in c.channels.items():
            weight = CHANNEL_WEIGHTS.get(channel, 0.5)
            rrf += weight * (1.0 / (RRF_K + rank + 1))

        quality_term = QUALITY_BOOST * c.quality
        importance_term = IMPORTANCE_BOOST * c.importance
        score = rrf + quality_term + importance_term

        results.append(
            RankedResult(
                memory_id=c.memory_id,
                score=round(score, 6),
                channels=sorted(c.channels.keys()),
                explanation={
                    "rrf": round(rrf, 6),
                    "quality_boost": round(quality_term, 6),
                    "importance_boost": round(importance_term, 6),
                },
            )
        )

    # Stable deterministic sort: score desc, then memory_id asc as tiebreak.
    results.sort(key=lambda r: (-r.score, r.memory_id))
    return results[:top_k]
