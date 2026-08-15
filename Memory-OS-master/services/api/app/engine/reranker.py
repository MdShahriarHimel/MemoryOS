"""Deterministic retrieval reranker.

Applies a second-stage feature-based reranking pass after RRF fusion. Uses
hand-crafted, auditable signals — no learned cross-encoder, no LLM:

  - Query–document token overlap (coverage)
  - Recency boost (observed_at / created_at)
  - Quality and importance from upstream ranking
  - Channel diversity bonus (multi-channel hits rank higher)

Identical inputs always produce identical orderings.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from app.engine.ranking import RankedResult
from app.engine.retrieval import tokenize


@dataclass
class RerankInput:
    memory_id: str
    content: str
    base: RankedResult
    observed_at: datetime | None
    created_at: datetime
    quality: float
    importance: float


@dataclass
class RerankedResult:
    memory_id: str
    score: float
    base_score: float
    rerank_boost: float
    channels: list[str]
    explanation: dict[str, float]


def _recency_score(observed_at: datetime | None, created_at: datetime, now: datetime) -> float:
    ref = observed_at or created_at
    if ref.tzinfo is None:
        ref = ref.replace(tzinfo=timezone.utc)
    age_days = max((now - ref).total_seconds() / 86400, 0)
    return 1.0 / (1.0 + age_days / 30.0)


def _overlap_score(query_tokens: set[str], doc_tokens: set[str]) -> float:
    if not query_tokens:
        return 0.0
    return len(query_tokens & doc_tokens) / len(query_tokens)


def rerank(
    query: str,
    candidates: list[RerankInput],
    *,
    top_k: int,
    now: datetime | None = None,
) -> list[RerankedResult]:
    now = now or datetime.now(timezone.utc)
    q_tokens = set(tokenize(query))
    results: list[RerankedResult] = []

    for c in candidates:
        doc_tokens = set(tokenize(c.content))
        overlap = _overlap_score(q_tokens, doc_tokens)
        recency = _recency_score(c.observed_at, c.created_at, now)
        diversity = 0.1 * (len(c.base.channels) - 1) if len(c.base.channels) > 1 else 0.0

        boost = (
            0.35 * overlap
            + 0.20 * recency
            + 0.15 * c.quality
            + 0.10 * c.importance
            + diversity
        )
        final = c.base.score + boost

        explanation = dict(c.base.explanation)
        explanation.update({
            "overlap": round(overlap, 6),
            "recency": round(recency, 6),
            "diversity": round(diversity, 6),
            "rerank_boost": round(boost, 6),
        })

        results.append(
            RerankedResult(
                memory_id=c.memory_id,
                score=round(final, 6),
                base_score=c.base.score,
                rerank_boost=round(boost, 6),
                channels=c.base.channels,
                explanation=explanation,
            )
        )

    results.sort(key=lambda r: (-r.score, r.memory_id))
    return results[:top_k]
