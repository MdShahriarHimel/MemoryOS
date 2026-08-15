# Architecture

MEMORY OS is a modular monolith with clean service boundaries. PostgreSQL is the
source of truth; Redis, Neo4j and OpenSearch back specific paths.

```
External AI Agent ──(REST / SDK / MCP)──► MEMORY OS
                                            │
   API Gateway · Auth · Memory Core · Lifecycle · Hybrid Retrieval
   Vector Search · Keyword Search · Ranking · Graph · Temporal
   Conflict · Provenance · Context Builder · Reflection · Sessions · Analytics
                                            │
        ┌───────────────┬──────────────────┼─────────────────┐
     PostgreSQL       Redis              Neo4j            OpenSearch
     + pgvector       cache/limits       graph            BM25
```

MEMORY OS never generates the final AI response and never runs an LLM.

## Determinism
Quality scoring (`engine/quality.py`), lifecycle (`engine/lifecycle.py`) and
ranking (`engine/ranking.py`) are pure functions of stored signals. Identical
inputs always produce identical outputs, so provenance can explain every score.
