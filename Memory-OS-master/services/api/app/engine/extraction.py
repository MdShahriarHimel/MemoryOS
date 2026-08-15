"""Deterministic memory extraction — model-independent.

No LLM calls. Uses rule-based pattern matching and accepts pre-structured facts
from external AI systems via the extraction contract.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class ExtractedFact:
    subject: str
    predicate: str
    value: str
    memory_type: str
    confidence: float
    polarity: str = "positive"  # positive | negative | neutral
    temporal_state: str = "current"  # current | historical
    valid_from: datetime | None = None
    supersedes: list[str] = field(default_factory=list)
    content: str = ""
    normalized_content: str = ""


@dataclass
class ExtractionResult:
    facts: list[ExtractedFact]
    method: str  # rules | structured | hybrid
    raw_content: str


# Deterministic patterns — ordered by specificity.
_PATTERNS: list[tuple[re.Pattern, str, str, float]] = [
    (re.compile(r"(?:I|User)\s+(?:don'?t|do not)\s+like\s+(.+?)\s+anymore", re.I),
     "preference", "dislikes", 0.88),
    (re.compile(r"(?:I|User)\s+(?:moved|move)\s+(?:from\s+\w+\s+)?(?:to|back to)\s+(.+?)(?:\.|$)", re.I),
     "location", "lives_in", 0.92),
    (re.compile(r"(?:I|User)\s+(?:returned|moved back)\s+to\s+(.+?)(?:\.|$)", re.I),
     "location", "lives_in", 0.93),
    (re.compile(r"(?:I|User)\s+(?:live|lives|am living)\s+in\s+(.+?)(?:\.|$)", re.I),
     "location", "lives_in", 0.90),
    (re.compile(r"(?:I|User)\s+(?:prefer|prefers)\s+(.+?)(?:\.|$)", re.I),
     "preference", "prefers", 0.85),
    (re.compile(r"(?:I|User)\s+(?:like|likes)\s+(.+?)(?:\.|$)", re.I),
     "preference", "likes", 0.82),
    (re.compile(r"(?:I|User)\s+(?:dislike|dislikes|hate|hates)\s+(.+?)(?:\.|$)", re.I),
     "preference", "dislikes", 0.84),
    (re.compile(r"(?:I|User)\s+(?:work|works)\s+(?:at|for)\s+(.+?)(?:\.|$)", re.I),
     "fact", "works_at", 0.88),
    (re.compile(r"(?:I|User)\s+(?:switched|switched to|uses|use)\s+(.+?)(?:\.|$)", re.I),
     "preference", "uses", 0.80),
    (re.compile(r"(?:I|User)\s+(?:manage|manages)\s+(.+?)(?:\.|$)", re.I),
     "fact", "manages", 0.83),
]


def _normalize(text: str) -> str:
    return " ".join(text.lower().strip().split())


def extract_from_content(
    content: str,
    *,
    subject: str = "user",
    source_type: str | None = None,
    structured_facts: list[dict] | None = None,
    now: datetime | None = None,
) -> ExtractionResult:
    """Extract structured facts from raw content using deterministic rules."""
    now = now or datetime.now(timezone.utc)
    facts: list[ExtractedFact] = []
    method = "rules"

    if structured_facts:
        method = "structured" if not content.strip() else "hybrid"
        for sf in structured_facts:
            facts.append(
                ExtractedFact(
                    subject=sf.get("subject", subject),
                    predicate=sf.get("predicate", "observation"),
                    value=str(sf.get("value", sf.get("object", ""))),
                    memory_type=sf.get("memory_type", "fact"),
                    confidence=float(sf.get("confidence", 0.9)),
                    polarity=sf.get("polarity", "positive"),
                    temporal_state=sf.get("temporal_state", "current"),
                    valid_from=sf.get("valid_from"),
                    supersedes=list(sf.get("supersedes", [])),
                    content=sf.get("content") or content,
                    normalized_content=_normalize(
                        f"{sf.get('subject', subject)} {sf.get('predicate', '')} {sf.get('value', '')}"
                    ),
                )
            )

    text = content.strip()
    if text:
        for pattern, memory_type, predicate, confidence in _PATTERNS:
            match = pattern.search(text)
            if match:
                value = match.group(1).strip().rstrip(".")
                polarity = "negative" if predicate in ("dislikes",) else "positive"
                if "don't" in text.lower() or "do not" in text.lower():
                    polarity = "negative"
                facts.append(
                    ExtractedFact(
                        subject=subject,
                        predicate=predicate,
                        value=value,
                        memory_type=memory_type,
                        confidence=confidence,
                        polarity=polarity,
                        temporal_state="current",
                        valid_from=now,
                        content=text,
                        normalized_content=_normalize(f"{subject} {predicate} {value}"),
                    )
                )
                break  # one primary fact per sentence pass

        if not facts and not structured_facts:
            # Fallback: store as unstructured observation with low extraction confidence
            facts.append(
                ExtractedFact(
                    subject=subject,
                    predicate="observation",
                    value=text[:200],
                    memory_type="observation",
                    confidence=0.5,
                    content=text,
                    normalized_content=_normalize(text),
                )
            )

    return ExtractionResult(facts=facts, method=method, raw_content=content)
