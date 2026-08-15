# Provenance (v0.3)

Every memory in MEMORY OS has traceable provenance explaining **why the system believes it exists**.

## Provenance fields

| Field | Description |
|-------|-------------|
| `source_type` | Origin type (conversation, api, document, etc.) |
| `source_id` | External source identifier |
| `observed_at` | When the fact was observed |
| `extracted_at` | When extraction occurred (if via extract API) |
| `derived_from[]` | Parent memory IDs this was derived from |
| `supersedes[]` | Memory IDs this version replaces |
| `evidence[]` | Supporting evidence records |

## API

```bash
GET /v1/memory/{id}/provenance
```

Response:

```json
{
  "memory_id": "m123",
  "source_type": "conversation",
  "source_id": "conv_42",
  "derived_from": ["m100"],
  "supersedes": ["m99"],
  "evidence": [{"origin": "memory.create"}],
  "confidence": 0.94
}
```

Provenance is created automatically on memory write and enriched on extraction/supersession.
