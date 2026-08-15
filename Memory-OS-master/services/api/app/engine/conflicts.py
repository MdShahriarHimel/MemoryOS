"""Advanced contradiction / conflict engine.

Extends basic lexical overlap detection with:
  - Negation polarity flip detection
  - Numeric/date divergence heuristics
  - Temporal validity overlap conflicts
  - Severity scoring for triage

Deterministic and auditable. Conflicts are surfaced as candidates; resolution
is always explicit (API or operator action).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from app.engine.retrieval import ConflictSignal, detect_conflicts, tokenize

_NEGATION = re.compile(r"\b(not|never|no longer|doesn't|don't|isn't|aren't|wasn't|weren't)\b")
_NUMBER = re.compile(r"\b\d+(?:\.\d+)?\b")
_DATE = re.compile(r"\b(20\d{2}|19\d{2})[-/](0?[1-9]|1[0-2])[-/](0?[1-9]|[12]\d|3[01])\b")


@dataclass
class ConflictReport:
    memory_a: str
    memory_b: str
    reason: str
    severity: float  # 0..1
    signals: list[str]


def _stem(tok: str) -> str:
    return tok[:-1] if len(tok) > 3 and tok.endswith("s") else tok


def _negation_flip(a_tokens: set[str], b_tokens: set[str]) -> bool:
    a_text = " ".join(a_tokens)
    b_text = " ".join(b_tokens)
    a_neg = bool(_NEGATION.search(a_text))
    b_neg = bool(_NEGATION.search(b_text))
    if a_neg == b_neg:
        return False
    core_a = {_stem(t) for t in a_tokens if t not in {"not", "never", "no", "longer", "does", "don", "isn", "aren't", "wasn", "weren"}}
    core_b = {_stem(t) for t in b_tokens if t not in {"not", "never", "no", "longer", "does", "don", "isn", "aren't", "wasn", "weren"}}
    overlap = len(core_a & core_b) / max(len(core_a | core_b), 1)
    return overlap >= 0.4


def _numeric_divergence(a_text: str, b_text: str) -> bool:
    na, nb = set(_NUMBER.findall(a_text)), set(_NUMBER.findall(b_text))
    if not na or not nb:
        return False
    shared_context = len(set(tokenize(a_text)) & set(tokenize(b_text))) >= 3
    return shared_context and na != nb


def _temporal_overlap_conflict(
    a_valid_from: datetime | None,
    a_valid_until: datetime | None,
    b_valid_from: datetime | None,
    b_valid_until: datetime | None,
) -> bool:
    if not any([a_valid_from, a_valid_until, b_valid_from, b_valid_until]):
        return False
    af = a_valid_from or datetime.min.replace(tzinfo=a_valid_from.tzinfo if a_valid_from else None)
    au = a_valid_until or datetime.max.replace(tzinfo=a_valid_until.tzinfo if a_valid_until else None)
    bf = b_valid_from or datetime.min.replace(tzinfo=b_valid_from.tzinfo if b_valid_from else None)
    bu = b_valid_until or datetime.max.replace(tzinfo=b_valid_until.tzinfo if b_valid_until else None)
    return af <= bu and bf <= au


@dataclass
class MemoryConflictInput:
    memory_id: str
    content: str
    valid_from: datetime | None = None
    valid_until: datetime | None = None


def analyze_conflicts(memories: list[MemoryConflictInput]) -> list[ConflictReport]:
    """Full conflict analysis pipeline."""
    base = detect_conflicts("", [(m.memory_id, m.content) for m in memories])
    by_id = {m.memory_id: m for m in memories}
    reports: list[ConflictReport] = []

    seen_pairs: set[tuple[str, str]] = set()

    def add(a_id: str, b_id: str, reason: str, severity: float, signals: list[str]) -> None:
        pair = tuple(sorted((a_id, b_id)))
        if pair in seen_pairs:
            return
        seen_pairs.add(pair)
        reports.append(ConflictReport(a_id, b_id, reason, round(severity, 4), signals))

    for sig in base:
        add(sig.memory_a, sig.memory_b, sig.reason, min(0.6 + sig.overlap * 0.3, 0.95), ["lexical_overlap"])

    tokenized = {m.memory_id: set(tokenize(m.content)) for m in memories}
    for i in range(len(memories)):
        for j in range(i + 1, len(memories)):
            a, b = memories[i], memories[j]
            signals: list[str] = []
            severity = 0.0

            if _negation_flip(tokenized[a.memory_id], tokenized[b.memory_id]):
                signals.append("negation_flip")
                severity = max(severity, 0.85)

            if _numeric_divergence(a.content, b.content):
                signals.append("numeric_divergence")
                severity = max(severity, 0.75)

            if _temporal_overlap_conflict(a.valid_from, a.valid_until, b.valid_from, b.valid_until):
                if tokenized[a.memory_id] & tokenized[b.memory_id]:
                    signals.append("temporal_overlap_same_subject")
                    severity = max(severity, 0.7)

            if signals:
                add(a.memory_id, b.memory_id, "+".join(signals), severity, signals)

    reports.sort(key=lambda r: (-r.severity, r.memory_a, r.memory_b))
    return reports


def to_legacy_signals(reports: list[ConflictReport]) -> list[ConflictSignal]:
    return [
        ConflictSignal(r.memory_a, r.memory_b, r.reason, r.severity)
        for r in reports
    ]
