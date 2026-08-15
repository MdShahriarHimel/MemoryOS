"""Token budget helpers for context builder v2 and MemoryBench."""
from __future__ import annotations

from app.engine.retrieval import tokenize


def estimate_tokens(text: str) -> int:
    """Deterministic token estimate (word-piece proxy)."""
    return max(1, len(tokenize(text)))


def pack_by_token_budget(
    items: list[tuple[str, str]],
    *,
    max_tokens: int,
) -> tuple[list[str], int, bool]:
    """Greedy pack of (id, text) tuples into max_tokens budget."""
    kept: list[str] = []
    used = 0
    for item_id, text in items:
        cost = estimate_tokens(text)
        if used + cost > max_tokens:
            break
        kept.append(item_id)
        used += cost
    truncated = len(kept) < len(items)
    return kept, used, truncated
