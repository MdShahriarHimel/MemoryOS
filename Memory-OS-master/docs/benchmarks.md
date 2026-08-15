# MemoryBench (v0.3)

MemoryBench is MEMORY OS's deterministic benchmark suite. It produces **real measurements only** — no fabricated performance claims.

## Categories

| Category | Status |
|----------|--------|
| `current_truth_resolution` | **tested** — engine-level deterministic tests |
| `fact_retrieval` | **tested** — extraction engine tests |
| `preference_retrieval` | **tested** — negation/polarity extraction |
| `temporal_retrieval` | **tested** — as-of truth resolution |
| `provenance` | **tested** — structured + rule extraction |
| `contradiction_resolution` | **tested** — negation conflict engine |
| `deduplication` | **tested** — fingerprint + Jaccard clustering |
| `entity_resolution` | **tested** — alias + fuzzy label merge |
| `multi_hop_retrieval` | **tested** — bounded graph BFS |
| `session_continuity` | **tested** — monotonic event sequence |
| `long_context_retrieval` | **tested** — context token budget path |
| `tenant_isolation` | **tested** — in-memory vector store isolation |

## Running benchmarks

```bash
curl -X POST localhost:8000/v1/benchmarks/run -d '{
  "name": "memorybench",
  "scale": 1000,
  "categories": ["current_truth_resolution", "fact_retrieval"]
}'
```

## Scale testing

| Scale | Status |
|-------|--------|
| 1K | Runnable in dev/test environment |
| 10K | Requires dedicated benchmark harness |
| 100K+ | Documented requirements only — not validated in CI |

Scale tests above 10K memories produce a note in results rather than fake numbers.

## Retrieval evaluation

The evaluation engine computes:

- Recall@K, Precision@K, MRR, NDCG
- Latency p50, p95, p99

Compare modes: `keyword`, `vector`, `hybrid`, `graph`, `hybrid+rerank`.
