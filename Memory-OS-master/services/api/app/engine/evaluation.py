"""Retrieval evaluation metrics — reproducible, deterministic."""
from __future__ import annotations

import math
from dataclasses import dataclass, field


@dataclass
class EvalQuery:
    query: str
    expected_memory_ids: list[str]
    relevance: dict[str, float] = field(default_factory=dict)


@dataclass
class EvalResult:
    query: str
    retrieved_ids: list[str]
    recall_at_k: dict[int, float] = field(default_factory=dict)
    precision_at_k: dict[int, float] = field(default_factory=dict)
    mrr: float = 0.0
    ndcg_at_k: dict[int, float] = field(default_factory=dict)
    latency_ms: float = 0.0


@dataclass
class EvalSummary:
    total_queries: int
    mean_recall_at_k: dict[int, float] = field(default_factory=dict)
    mean_precision_at_k: dict[int, float] = field(default_factory=dict)
    mean_mrr: float = 0.0
    mean_ndcg_at_k: dict[int, float] = field(default_factory=dict)
    latency_p50_ms: float = 0.0
    latency_p95_ms: float = 0.0
    latency_p99_ms: float = 0.0
    mode: str = ""


def _recall_at_k(retrieved: list[str], expected: set[str], k: int) -> float:
    if not expected:
        return 0.0
    top_k = retrieved[:k]
    hits = sum(1 for r in top_k if r in expected)
    return hits / len(expected)


def _precision_at_k(retrieved: list[str], expected: set[str], k: int) -> float:
    if k == 0:
        return 0.0
    top_k = retrieved[:k]
    hits = sum(1 for r in top_k if r in expected)
    return hits / k


def _mrr(retrieved: list[str], expected: set[str]) -> float:
    for i, rid in enumerate(retrieved):
        if rid in expected:
            return 1.0 / (i + 1)
    return 0.0


def _ndcg_at_k(
    retrieved: list[str], relevance: dict[str, float], k: int
) -> float:
    top_k = retrieved[:k]
    dcg = sum(
        (2 ** relevance.get(rid, 0.0) - 1) / math.log2(i + 2)
        for i, rid in enumerate(top_k)
    )
    ideal = sorted(relevance.values(), reverse=True)[:k]
    idcg = sum(
        (2 ** rel - 1) / math.log2(i + 2)
        for i, rel in enumerate(ideal)
    )
    return dcg / idcg if idcg > 0 else 0.0


def evaluate_query(
    eq: EvalQuery,
    retrieved_ids: list[str],
    *,
    k_values: list[int] | None = None,
    latency_ms: float = 0.0,
) -> EvalResult:
    k_values = k_values or [1, 3, 5, 10]
    expected = set(eq.expected_memory_ids)
    rel = eq.relevance or {mid: 1.0 for mid in expected}

    result = EvalResult(query=eq.query, retrieved_ids=retrieved_ids, latency_ms=latency_ms)
    for k in k_values:
        result.recall_at_k[k] = _recall_at_k(retrieved_ids, expected, k)
        result.precision_at_k[k] = _precision_at_k(retrieved_ids, expected, k)
        result.ndcg_at_k[k] = _ndcg_at_k(retrieved_ids, rel, k)
    result.mrr = _mrr(retrieved_ids, expected)
    return result


def summarize_results(results: list[EvalResult], *, mode: str = "") -> EvalSummary:
    if not results:
        return EvalSummary(total_queries=0, mode=mode)

    k_values = list(results[0].recall_at_k.keys())
    latencies = sorted(r.latency_ms for r in results)
    n = len(latencies)

    def percentile(p: float) -> float:
        idx = min(int(n * p), n - 1)
        return latencies[idx]

    summary = EvalSummary(
        total_queries=len(results),
        mean_mrr=sum(r.mrr for r in results) / len(results),
        latency_p50_ms=percentile(0.5),
        latency_p95_ms=percentile(0.95),
        latency_p99_ms=percentile(0.99),
        mode=mode,
    )
    for k in k_values:
        summary.mean_recall_at_k[k] = sum(r.recall_at_k[k] for r in results) / len(results)
        summary.mean_precision_at_k[k] = sum(r.precision_at_k[k] for r in results) / len(results)
        summary.mean_ndcg_at_k[k] = sum(r.ndcg_at_k[k] for r in results) / len(results)
    return summary
