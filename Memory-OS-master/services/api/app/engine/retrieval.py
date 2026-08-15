"""Hybrid retrieval orchestration + deterministic keyword scoring.

Combines vector, keyword and (optional) graph channels, then hands candidates to
the ranking engine. Produces an honest retrieval trace with real counts — never
fabricated numbers.

Keyword scoring here is a deterministic BM25-lite over stored content. In a full
deployment OpenSearch handles this; the abstraction lets it swap in without
changing the pipeline.
"""
from __future__ import annotations

import math
import re
import time
from collections import Counter
from dataclasses import dataclass, field

_TOKEN = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


@dataclass
class KeywordDoc:
    memory_id: str
    tokens: list[str]


@dataclass
class RetrievalTrace:
    query: str
    vector_candidates: int = 0
    keyword_candidates: int = 0
    graph_candidates: int = 0
    merged_candidates: int = 0
    final_results: int = 0
    latency_ms: int = 0

    def as_dict(self) -> dict:
        return {
            "query": self.query,
            "vector_candidates": self.vector_candidates,
            "keyword_candidates": self.keyword_candidates,
            "graph_candidates": self.graph_candidates,
            "merged_candidates": self.merged_candidates,
            "final_results": self.final_results,
            "latency_ms": self.latency_ms,
        }


class BM25Lite:
    """Deterministic BM25 over an in-memory corpus (dev / test / fallback)."""

    K1 = 1.5
    B = 0.75

    def __init__(self, docs: list[KeywordDoc]) -> None:
        self.docs = docs
        self.df: Counter[str] = Counter()
        for d in docs:
            for t in set(d.tokens):
                self.df[t] += 1
        self.n = len(docs)
        self.avgdl = (sum(len(d.tokens) for d in docs) / self.n) if self.n else 0.0

    def search(self, query: str, *, limit: int) -> list[tuple[str, float]]:
        q_terms = tokenize(query)
        scored: list[tuple[str, float]] = []
        for d in self.docs:
            tf = Counter(d.tokens)
            score = 0.0
            dl = len(d.tokens)
            for term in q_terms:
                if term not in tf:
                    continue
                idf = math.log(1 + (self.n - self.df[term] + 0.5) / (self.df[term] + 0.5))
                denom = tf[term] + self.K1 * (1 - self.B + self.B * (dl / (self.avgdl or 1)))
                score += idf * (tf[term] * (self.K1 + 1)) / denom
            if score > 0:
                scored.append((d.memory_id, score))
        scored.sort(key=lambda x: (-x[1], x[0]))
        return scored[:limit]


@dataclass
class ConflictSignal:
    memory_a: str
    memory_b: str
    reason: str
    overlap: float


def detect_conflicts(
    subject_key: str, memories: list[tuple[str, str]]
) -> list[ConflictSignal]:
    """Deterministic contradiction candidate detection.

    memories: list of (memory_id, content). Flags memories that share a strong
    lexical subject overlap but differ in their object — a heuristic surfacing
    *candidates* for human review. It never auto-resolves.
    """
    signals: list[ConflictSignal] = []
    tokenized = [(mid, set(tokenize(content))) for mid, content in memories]
    for i in range(len(tokenized)):
        for j in range(i + 1, len(tokenized)):
            a_id, a = tokenized[i]
            b_id, b = tokenized[j]
            if not a or not b:
                continue
            overlap = len(a & b) / len(a | b)
            differ = len(a ^ b)
            # High shared context but meaningful divergence → candidate conflict.
            if overlap >= 0.4 and differ >= 2:
                signals.append(
                    ConflictSignal(
                        memory_a=a_id,
                        memory_b=b_id,
                        reason=f"shared_subject_overlap={overlap:.2f}",
                        overlap=round(overlap, 4),
                    )
                )
    return signals


class Stopwatch:
    def __enter__(self):
        self._t = time.perf_counter()
        return self

    def __exit__(self, *a):
        self.elapsed_ms = int((time.perf_counter() - self._t) * 1000)
