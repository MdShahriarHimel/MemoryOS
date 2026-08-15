# Production features

Enterprise-grade capabilities added in v0.2. Each feature is real and
testable; optional dependencies degrade gracefully when not configured.

## PostgreSQL RLS hardening

Migration `0002_rls_metering_audit` enables `FORCE ROW LEVEL SECURITY` on all
tenant-scoped tables. Policies compare `tenant_id` to the session variable
`app.current_tenant`, set on every authenticated request via `set_rls_tenant()`.

Application-layer tenant filters remain the primary guard; RLS is defense in
depth for direct SQL access and connection pool mistakes.

## Rate limiting

`RateLimitMiddleware` applies a sliding-window limit per tenant (default 120 RPM +
burst). Uses Redis when `REDIS_URL` is set; falls back to in-process counters
for zero-dependency dev runs.

Headers: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `Retry-After`.

## OpenTelemetry

Set `OTEL_ENABLED=true` and `OTEL_EXPORTER_ENDPOINT`. Requires optional OTEL
packages from `requirements.txt` comments. No-op when disabled.

## Prometheus / Grafana

- Metrics endpoint: `GET /metrics`
- Docker Compose: Prometheus `:9090`, Grafana `:3001` (admin / `memoryos`)
- Dashboard: `infra/monitoring/grafana/dashboards/memory-os.json`

## Advanced memory deduplication

`GET /v1/operations/deduplication` — fingerprint + Jaccard + optional embedding
cosine clustering. Engine: `app/engine/deduplication.py`.

## Advanced contradiction / conflict engine

`GET /v1/operations/conflicts` — negation flip, numeric divergence, temporal
overlap heuristics. Engine: `app/engine/conflicts.py`.

## Temporal versioning

`GET /v1/operations/temporal/as-of?as_of=...` — point-in-time validity.
`GET /v1/operations/temporal/lineage` — supersedes chains.
Engine: `app/engine/temporal.py`.

## Memory consolidation / reflection

`POST /v1/operations/reflection` — merge/archive/conflict/provenance action plan.
Celery task `run_reflection` uses the same consolidation engine.
Engine: `app/engine/consolidation.py`.

## Retrieval reranker

Search requests accept `rerank: true` (default). Second-stage deterministic
reranking after RRF fusion. Engine: `app/engine/reranker.py`.

## S3 / object storage

`app/storage/object_store.py` — `LocalObjectStore` (dev) and `S3ObjectStore`
(MinIO/S3). Configure via `OBJECT_STORAGE_BACKEND`, `S3_*`, `AWS_*`.

## Audit log system

Append-only `audit_logs` with structured `details`. Mutating requests logged
via `AuditMiddleware`. Query: `GET /v1/audit/logs` (admin).

## Usage metering

Hourly counters in `usage_meters`. Middleware increments on write/search/API
paths. Summary: `GET /v1/metering/usage`.

## Production-grade CLI

```bash
pip install -e packages/cli
memoryos health
memoryos memory-create "User prefers dark mode"
memoryos memory-search "dark mode"
memoryos usage
memoryos reflect
```

Env: `MEMORY_OS_API_URL`, `MEMORY_OS_TOKEN`.

## Developer portal

- API index: `GET /developer`
- Dashboard: `/developer`
- Enhanced OpenAPI tags at `/docs` and `/redoc`

## SDK CI

GitHub Actions workflow `.github/workflows/sdk-ci.yml` compiles/tests Python,
TypeScript, Go, Rust, Java, and Kotlin SDKs on every `packages/**` change.
