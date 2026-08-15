# Memory model

A `Memory` is the first-class entity. Key fields: content, memory_type, importance,
confidence, reliability, temporal columns (valid_from/valid_until/observed_at/
superseded_at), version, status, provenance, parent/supersedes links.

Types: episodic, semantic, procedural, preference, fact, decision, goal, task,
relationship, observation, event, profile, system, custom.

Embeddings live in `memory_embeddings` and are **always client-supplied**. If a
required embedding is missing or the wrong dimension, the API returns a structured
`EMBEDDING_REQUIRED` validation error — it is never generated server-side.
