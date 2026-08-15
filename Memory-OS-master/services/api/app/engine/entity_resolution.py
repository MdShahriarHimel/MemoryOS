"""Deterministic entity resolution — no LLM.

Merges entity labels that refer to the same real-world entity using normalized
keys, alias tables, and fuzzy Jaccard matching on labels.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.engine.deduplication import jaccard, normalize_content
from app.engine.retrieval import tokenize

_WS = re.compile(r"\s+")


def normalize_entity_key(label: str) -> str:
    return _WS.sub("_", normalize_content(label))


@dataclass
class EntityCandidate:
    key: str
    label: str
    entity_type: str = "Person"
    aliases: list[str] = field(default_factory=list)
    memory_ids: list[str] = field(default_factory=list)
    confidence: float = 0.0


@dataclass
class EntityMergeGroup:
    canonical_key: str
    canonical_label: str
    merged_keys: list[str]
    reason: str
    score: float


# Common alias pairs (deterministic, extensible via API metadata)
_BUILTIN_ALIASES: dict[str, str] = {
    "bob": "robert",
    "rob": "robert",
    "bill": "william",
    "liz": "elizabeth",
    "dhaka": "dhaka_city",
    "dacca": "dhaka_city",
}


def _alias_root(key: str) -> str:
    return _BUILTIN_ALIASES.get(key, key)


def resolve_entities(
    candidates: list[EntityCandidate],
    *,
    jaccard_threshold: float = 0.75,
) -> tuple[list[EntityMergeGroup], list[EntityCandidate]]:
    """Return merge groups and resolved canonical entities."""
    if not candidates:
        return [], []

    by_key: dict[str, EntityCandidate] = {}
    for c in candidates:
        nk = normalize_entity_key(c.label)
        if nk in by_key:
            existing = by_key[nk]
            existing.aliases.extend(c.aliases)
            existing.memory_ids.extend(c.memory_ids)
            existing.confidence = max(existing.confidence, c.confidence)
        else:
            by_key[nk] = EntityCandidate(
                key=c.key or nk,
                label=c.label,
                entity_type=c.entity_type,
                aliases=list(c.aliases),
                memory_ids=list(c.memory_ids),
                confidence=c.confidence,
            )

    keys = list(by_key.keys())
    merged: set[str] = set()
    groups: list[EntityMergeGroup] = []

    for i, ka in enumerate(keys):
        if ka in merged:
            continue
        ta = set(tokenize(by_key[ka].label))
        root_a = _alias_root(ka)
        cluster = [ka]
        for kb in keys[i + 1 :]:
            if kb in merged:
                continue
            root_b = _alias_root(kb)
            if root_a == root_b:
                cluster.append(kb)
                continue
            tb = set(tokenize(by_key[kb].label))
            if jaccard(ta, tb) >= jaccard_threshold:
                cluster.append(kb)

        if len(cluster) > 1:
            canonical = max(cluster, key=lambda k: by_key[k].confidence)
            for k in cluster:
                merged.add(k)
            groups.append(
                EntityMergeGroup(
                    canonical_key=canonical,
                    canonical_label=by_key[canonical].label,
                    merged_keys=[k for k in cluster if k != canonical],
                    reason="alias_or_fuzzy_match",
                    score=max(by_key[k].confidence for k in cluster),
                )
            )

    resolved = [by_key[k] for k in keys if k not in merged]
    for g in groups:
        canon = by_key[g.canonical_key]
        for mk in g.merged_keys:
            canon.aliases.append(by_key[mk].label)
            canon.memory_ids.extend(by_key[mk].memory_ids)
        resolved.append(canon)
    return groups, resolved
