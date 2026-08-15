"""Human-readable summaries for retrieval explanation dicts."""
from __future__ import annotations


def summarize_explanation(explanation: dict[str, float], *, top_n: int = 3) -> str:
    if not explanation:
        return "No ranking signals recorded."
    ranked = sorted(explanation.items(), key=lambda kv: -abs(kv[1]))[:top_n]
    parts = [f"{name} ({score:+.3f})" for name, score in ranked]
    return "Ranked by: " + ", ".join(parts)
