# Temporal Memory (v0.3)

MEMORY OS supports bi-temporal memory versioning with deterministic truth resolution.

## Concepts

- **valid_from / valid_until** — when a fact was true in the real world
- **observed_at** — when the system learned the fact
- **supersedes / superseded_by** — version lineage chains
- **current truth** — resolved from the newest non-superseded memory per subject+predicate
- **historical truth** — point-in-time resolution via as-of queries

## APIs

| Method | Path | Description |
|--------|------|-------------|
| POST | `/v1/memory/as-of` | Query truths and valid memories at a point in time |
| GET | `/v1/memory/{id}/timeline` | Supersession chain for a memory |
| POST | `/v1/memory` with `supersedes[]` | Create a new version that supersedes prior memories |

## Example

```bash
# Create location history
curl -X POST localhost:8000/v1/memory -d '{
  "content": "User lives in Sylhet",
  "subject": "user", "predicate": "lives_in", "object_value": "Sylhet",
  "observed_at": "2024-01-01T00:00:00Z"
}'

# Supersede with new location
curl -X POST localhost:8000/v1/memory -d '{
  "content": "User moved to Dhaka",
  "subject": "user", "predicate": "lives_in", "object_value": "Dhaka",
  "supersedes": ["<previous_id>"],
  "observed_at": "2025-01-01T00:00:00Z"
}'

# Query historical truth
curl -X POST localhost:8000/v1/memory/as-of -d '{
  "as_of": "2025-06-01T00:00:00Z",
  "subject": "user", "predicate": "lives_in"
}'
```

Historical memories are **never deleted** — they remain queryable via timeline and as-of APIs.
