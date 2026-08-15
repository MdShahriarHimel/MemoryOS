# Retrieval

Pipeline: vector retrieval + keyword (BM25) retrieval → candidate fusion (RRF) →
deterministic ranking (quality + importance boosts) → top-K → context builder.

Every search returns a retrieval trace with **real** counts:
`{vector_candidates, keyword_candidates, graph_candidates, merged_candidates,
final_results, latency_ms}`. These are measured, never fabricated.

Ranking uses Reciprocal Rank Fusion with per-channel weights and a stable
tiebreak on memory id, so results are fully reproducible.
