# Enterprise Deployment Guide

This checklist maps to the 18-step enterprise readiness program for MEMORY OS v0.3+.

## Pre-flight checklist

| Step | Requirement | How to verify |
|------|-------------|---------------|
| 1 | Full test suite green | `make test-all` + CI (api-ci, dashboard-ci, sdk-ci) |
| 2 | Every API route smoke-tested | `tests/test_enterprise.py::test_full_api_smoke` |
| 3 | PostgreSQL RLS enabled | `alembic upgrade head` + `tests/test_rls_postgres.py` |
| 4 | Tenant isolation | `tests/test_enterprise.py::test_tenant_isolation_cross_tenant` |
| 5 | Temporal truth | `tests/test_enterprise.py::test_temporal_truth_api` |
| 6 | Conflicts | `tests/test_enterprise.py::test_operations_conflicts_and_dedup` |
| 7 | Deduplication | Same + `GET /v1/operations/deduplication` |
| 8 | Delete cascade | `tests/test_enterprise.py::test_delete_cascade_stores` |
| 9 | Idempotency | `tests/test_enterprise.py::test_idempotency_create` |
| 10 | Async workers | `docker compose -f docker-compose.yml -f docker-compose.prod.yml up worker` |
| 11 | MemoryBench categories | `POST /v1/benchmarks/run` — 12 categories (some require live DB harness) |
| 12 | Explainable retrieval | Search results include `explanation` + `explanation_summary` |
| 13 | Entity resolution | `GET /v1/operations/entity-resolution` |
| 14 | Load test | `make load-test` (requires [k6](https://k6.io)) |
| 15 | Security audit | See [security.md](security.md) + disable anon mode |
| 16 | Docker production | `make docker-prod` |
| 17 | Documentation | README + this guide |
| 18 | Enterprise ready | All rows above green |

## Production deploy

### 1. Secrets

```bash
export JWT_SECRET=$(openssl rand -hex 32)
export API_KEY_PEPPER=$(openssl rand -hex 32)
export METRICS_TOKEN=$(openssl rand -hex 32)
```

### 2. Start production stack

```bash
cp .env.example .env
# Edit .env with strong secrets
docker compose -f docker-compose.yml -f docker-compose.prod.yml up --build -d
```

Production profile enforces:

- `MEMORY_OS_ALLOW_ANON=false`
- Required `JWT_SECRET`, `API_KEY_PEPPER`, and `METRICS_TOKEN`
- Startup validation rejects weak secrets and anon mode
- Celery worker + beat services
- Restart policies and resource limits

### 3. Migrations

Migrations run automatically on API container start when `DATABASE_URL` is Postgres.

Manual run:

```bash
cd services/api && alembic upgrade head
```

Kubernetes (run before scaling API pods):

```bash
kubectl apply -f infra/kubernetes/00-namespace.yaml
kubectl apply -f infra/kubernetes/01-config-secrets.yaml
kubectl apply -f infra/kubernetes/05-migrate-job.yaml
kubectl wait --for=condition=complete job/memoryos-migrate -n memory-os --timeout=300s
kubectl apply -f infra/kubernetes/10-api.yaml
```

### 4. RLS verification (Postgres)

```sql
SET app.current_tenant = 'tenant-a';
SELECT COUNT(*) FROM memories WHERE tenant_id = 'tenant-b';  -- expect 0
```

Or run:

```bash
TEST_DATABASE_URL=postgresql+asyncpg://memoryos:memoryos@localhost:5432/memoryos \
  PYTHONPATH=. python -m pytest tests/test_rls_postgres.py -v
```

### 5. Load testing

```bash
# Production (API key required)
K6_API_URL=http://localhost:8000 K6_API_KEY=mos_your_key k6 run scripts/load/k6-smoke.js

# Local dev with anon mode
K6_ALLOW_ANON=true k6 run scripts/load/k6-smoke.js
```

SLO targets (smoke):

- Error rate < 5%
- p95 latency < 2s for health/create/search

### 6. Idempotency

Send `Idempotency-Key` header on `POST /v1/memory`:

```bash
curl -X POST localhost:8000/v1/memory \
  -H "Authorization: Bearer mos_..." \
  -H "Idempotency-Key: create-001" \
  -d '{"content":"Stable write"}'
```

Replay within 24h returns the same memory ID.

### 7. GDPR delete cascade

`POST /v1/memory/delete` cleans:

- Postgres memory rows (soft or hard)
- pgvector embeddings
- Graph edges (`source_memory_id`)
- Conflict records
- Object storage keys in `metadata.object_key`

Response includes `stores_cleaned` array.

## Kubernetes

Manifests under `infra/kubernetes/`:

- `05-migrate-job.yaml` — Alembic migration Job (run once per release)
- `10-api.yaml` — API deployment + HPA + readiness on `/v1/ready`
- `20-worker.yaml` — Celery worker
- `30-dashboard.yaml` — Next.js dashboard

Apply after configuring secrets and Postgres (see migration Job in step 3).

## Monitoring

- Prometheus: `:9090` (prod overlay uses bearer auth for scrape targets)
- Alertmanager: `:9093` (prod overlay; wire receivers in `infra/monitoring/alertmanager.yml`)
- Grafana: `:3001`
- API metrics: `GET /metrics` (requires `METRICS_TOKEN` in production)
- Audit log: `GET /v1/audit/logs` (admin)

## Known production gaps

- Set `QUOTA_ENFORCEMENT_ENABLED=true` in production to activate monthly limits
- Set `ALERTMANAGER_WEBHOOK_URL` for real paging (Slack/PagerDuty webhook)
- SDK packages are build-ready but require your npm/PyPI credentials to publish
- Full multi-store cascade verification requires Docker stack with OpenSearch + Neo4j
