"""Advanced deterministic memory deduplication.

Finds near-duplicate memories using a multi-signal fingerprint:
  1. Normalized content hash (exact dupes)
  2. Jaccard token overlap (near dupes)
  3. Optional embedding cosine similarity (when vectors exist)

Fully deterministic — no LLM, no learned model. Results are candidates for
consolidation; nothing is auto-deleted.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from app.engine.retrieval import tokenize

_WS = re.compile(r"\s+")


def normalize_content(text: str) -> str:
    return _WS.sub(" ", text.strip().lower())


def content_fingerprint(text: str) -> str:
    return hashlib.sha256(normalize_content(text).encode()).hexdigest()[:16]


def jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


def cosine(a: list[float], b: list[float]) -> float:
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(x * x for x in b) ** 0.5
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


@dataclass
class DuplicateCluster:
    canonical_id: str
    duplicate_ids: list[str]
    reason: str
    score: float


@dataclass
class MemoryRecord:
    memory_id: str
    content: str
    embedding: list[float] | None = None


def find_duplicates(
    memories: list[MemoryRecord],
    *,
    jaccard_threshold: float = 0.85,
    cosine_threshold: float = 0.92,
) -> list[DuplicateCluster]:
    """Return duplicate clusters sorted by score descending."""
    by_fp: dict[str, list[str]] = {}
    tokenized: dict[str, set[str]] = {}
    for m in memories:
        fp = content_fingerprint(m.content)
        by_fp.setdefault(fp, []).append(m.memory_id)
        tokenized[m.memory_id] = set(tokenize(m.content))

    clusters: list[DuplicateCluster] = []
    seen: set[str] = set()

    # Exact fingerprint clusters
    for fp, ids in by_fp.items():
        if len(ids) > 1:
            canonical = min(ids)
            dupes = [i for i in ids if i != canonical]
            for i in ids:
                seen.add(i)
            clusters.append(
                DuplicateCluster(canonical, dupes, "exact_fingerprint", 1.0)
            )

    # Near-duplicate via Jaccard + optional cosine
    ids = [m.memory_id for m in memories if m.memory_id not in seen]
    embed_by_id = {m.memory_id: m.embedding for m in memories}
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            a, b = ids[i], ids[j]
            jac = jaccard(tokenized[a], tokenized[b])
            cos = 0.0
            ea, eb = embed_by_id.get(a), embed_by_id.get(b)
            if ea is not None and eb is not None:
                cos = cosine(ea, eb)
            if jac >= jaccard_threshold or cos >= cosine_threshold:
                score = max(jac, cos)
                canonical = min(a, b)
                dupe = max(a, b)
                clusters.append(
                    DuplicateCluster(canonical, [dupe], "near_duplicate", round(score, 4))
                )

    clusters.sort(key=lambda c: (-c.score, c.canonical_id))
    return clusters
