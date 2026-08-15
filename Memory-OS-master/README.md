# MEMORY OS

**Model-independent cognitive memory infrastructure for AI agents.**

MEMORY OS v0.3 is durable, tenant-isolated memory you plug into any LLM stack. It stores facts, resolves temporal truth, fuses hybrid retrieval (vector + keyword + graph), and returns explainable context bundles — without running an LLM or embedding model inside the service.

Clients supply embeddings. MEMORY OS owns storage, lifecycle, retrieval, provenance, and audit.

---

## Table of contents

- [Why MEMORY OS](#why-memory-os)
- [Features](#features)
- [Architecture](#architecture)
- [Repository layout](#repository-layout)
- [Quick start](#quick-start)
- [Configuration](#configuration)
- [Authentication & RBAC](#authentication--rbac)
- [API reference](#api-reference)
- [Dashboard](#dashboard)
- [SDKs & CLI](#sdks--cli)
- [MCP server](#mcp-server)
- [Testing](#testing)
- [Production deployment](#production-deployment)
- [Security & compliance](#security--compliance)
- [Observability](#observability)
- [Documentation](#documentation)
- [Known limitations](#known-limitations)
- [Contributing](#contributing)
- [License](#license)

---

## Why MEMORY OS

| Problem | MEMORY OS approach |
|---------|-------------------|
| Chat history ≠ memory | Canonical memory records with lifecycle, confidence, and supersession |
| Vector-only retrieval misses structure | Hybrid fusion: pgvector + BM25 + graph + temporal channels |
| “What was true on date X?” | Temporal truth engine with `as-of` queries and timelines |
| Multi-tenant agents | PostgreSQL RLS, scoped API keys, append-only audit trail |
| Black-box RAG | Explainable retrieval scores + provenance chains |
| Vendor lock-in to one model | **No LLM inside** — works with any upstream model |

---

## Features

### Core memory (v0.3)

- **CRUD** — create, read, update, delete with tenant isolation
- **Hybrid search** — `vector`, `keyword`, `graph`, `temporal`, `hybrid` modes
- **Context builder** — token-budgeted bundles for agent prompts
- **Extraction** — deterministic rule-based fact extraction (no LLM)
- **Temporal truth** — supersession chains, `as-of` queries, timelines
- **Provenance** — full derivation chain per memory
- **Idempotency** — `Idempotency-Key` header on writes
- **GDPR** — export + cross-store delete (Postgres, pgvector, graph edges, object storage)

### Operations

- Deduplication clusters
- Conflict detection (negation, contradiction signals)
- Reflection planner + explicit execute endpoint
- Entity resolution
- MemoryBench (12 benchmark categories)
- Agent sessions + replay events

### Platform

- JWT + refresh rotation for dashboard users
- Scoped API keys (`mos_…`) for agents / SDK / MCP
- 5-role RBAC: `viewer` → `analyst` → `developer` → `admin` → `owner`
- Rate limiting (Redis-backed when configured)
- Usage metering (counters; no hard billing quotas)
- Webhooks with SSRF protection + encrypted secrets
- Celery workers (consolidation, webhook delivery)
- Prometheus metrics + optional OpenTelemetry

---

## Architecture

```
External AI Agent ──(REST / SDK / MCP)──► MEMORY OS API
                                            │
   Auth · RBAC · Memory Core · Hybrid Retrieval · Temporal Truth
   Conflict · Provenance · Context Builder · Reflection · Sessions
                                            │
        ┌───────────────┬──────────────────┼─────────────────┐
     PostgreSQL       Redis              Neo4j            OpenSearch
     + pgvector       cache/limits       graph (opt)      keyword (opt)
        │
     MinIO / S3 (object storage)
```

MEMORY OS is a **modular monolith**: one FastAPI service with clean engine boundaries. PostgreSQL is the source of truth. Optional stores degrade gracefully when not configured.

See [docs/architecture.md](docs/architecture.md) for design rationale.

---

## Repository layout

```
memory-os/
├── services/
│   ├── api/                 # FastAPI backend (Python 3.12)
│   │   ├── app/             # Routes, engines, middleware, security
│   │   ├── alembic/         # Database migrations
│   │   ├── tests/           # pytest suite (58+ tests)
│   │   ├── Dockerfile       # Production image (entrypoint runs migrations)
│   │   └── entrypoint.sh    # alembic upgrade head + uvicorn
│   └── worker/              # Celery worker + beat
├── dashboard/               # Next.js 15 admin UI
├── packages/
│   ├── sdk-python/          # Official Python SDK (pip installable)
│   ├── sdk-typescript/      # Official TypeScript SDK (@memory-os/sdk)
│   ├── sdk-go/              # Go client
│   ├── sdk-java/            # Java client
│   ├── sdk-kotlin/          # Kotlin client
│   ├── sdk-rust/            # Rust client
│   └── cli/                 # Typer CLI (`memoryos`)
├── mcp/                     # MCP tool server + Dockerfile
├── scripts/
│   ├── mcp_stdio_server.py  # Cursor / Claude MCP entrypoint
│   └── load/k6-smoke.js     # Load test harness
├── infra/
│   ├── kubernetes/          # K8s manifests (API, worker, dashboard)
│   └── monitoring/          # Prometheus + Grafana provisioning
├── docs/                    # Deep-dive guides
├── docker-compose.yml       # Full local stack
├── docker-compose.prod.yml  # Production overlay
├── Makefile                 # Common tasks
└── .env.example             # Environment template
```

---

## Quick start

### Prerequisites

- **Docker Desktop** (recommended) — Postgres, Redis, Neo4j, OpenSearch, MinIO, API, Dashboard, Prometheus, Grafana
- **Or minimal local:** Python 3.12+, Node 20+

### Option A — Docker Compose (recommended)

```bash
cp .env.example .env
docker compose up --build
```

| Service | URL |
|---------|-----|
| API | http://localhost:8000 |
| Swagger docs | http://localhost:8000/docs |
| Developer portal | http://localhost:8000/developer |
| Dashboard | http://localhost:3000 |
| Grafana | http://localhost:3001 (admin / `memoryos`) |
| Prometheus | http://localhost:9090 |
| MinIO console | http://localhost:9001 |
| Neo4j browser | http://localhost:7474 |

Migrations run **automatically** on API container start when `DATABASE_URL` is Postgres (`entrypoint.sh`).

First login: open http://localhost:3000/login → register an account.

### Option B — Local development (minimal)

No Docker required for core API tests (SQLite fallback).

**Terminal 1 — API:**

```bash
cd services/api
pip install -r requirements.txt
export PYTHONPATH=.
export DATABASE_URL="sqlite+aiosqlite:///./memory_os.db"
export MEMORY_OS_ALLOW_ANON=true
export EMBEDDING_DIM=4
uvicorn app.main:app --reload --port 8000
```

**Terminal 2 — Dashboard:**

```bash
cd dashboard
npm install
export NEXT_PUBLIC_MEMORY_OS_API_URL=http://localhost:8000
export MEMORY_OS_API_URL=http://localhost:8000
npm run dev
```

Open http://localhost:3000 and register.

### Makefile shortcuts

```bash
make docker-up      # Full Docker stack
make docker-prod    # Production overlay
make api-test       # pytest (services/api)
make test-all       # pytest + dashboard typecheck + build
make sdk-test       # Python compile + TS SDK build
make load-test      # k6 smoke (requires k6 installed)
make dev            # Dashboard dev server
```

---

## Configuration

Copy `.env.example` to `.env`. Key variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | SQLite file | Postgres recommended for production |
| `REDIS_URL` | — | Enables Redis-backed rate limiting + Celery |
| `NEO4J_URI` | — | Graph store (optional) |
| `OPENSEARCH_URL` | — | Keyword index (optional; in-process BM25 fallback) |
| `EMBEDDING_DIM` | `1536` | Expected embedding vector length from clients |
| `JWT_SECRET` | change-me | HS256 signing secret (≥32 chars in production) |
| `API_KEY_PEPPER` | change-me | Mixed into API key hashes at rest |
| `MEMORY_OS_ALLOW_ANON` | `false` | Allow unauthenticated access with `X-Tenant-ID` (dev only) |
| `METRICS_TOKEN` | — | Protects `/metrics` (required in production) |
| `RATE_LIMIT_RPM` | `120` | Requests per minute per tenant |
| `POSTGRES_RLS_ENABLED` | `true` | Row-level security on Postgres |
| `PROMETHEUS_ENABLED` | `true` | Expose `/metrics` |
| `NEXT_PUBLIC_MEMORY_OS_API_URL` | `http://localhost:8000` | Dashboard → API (browser) |
| `MEMORY_OS_API_URL` | — | Dashboard server-side proxy to API (Docker: `http://api:8000`) |

There are **deliberately no LLM or embedding provider keys** in this project.

---

## Authentication & RBAC

Two bearer-token methods:

| Method | Header | Use case |
|--------|--------|----------|
| **JWT** | `Authorization: Bearer <access_token>` | Dashboard users (`/v1/auth/login`) |
| **API key** | `Authorization: Bearer mos_<secret>` | Agents, SDKs, MCP |

**Roles** (hierarchy): `viewer` → `analyst` → `developer` → `admin` → `owner`

**API key scopes:** `memory:read`, `memory:write`, `graph:read`, `sessions:read`, `analytics:read`, `admin`

**Write guard:** JWT `viewer` cannot write memory. API keys need explicit `memory:write` (or `admin`).

**Dashboard auth:** Refresh token in httpOnly cookie; access token in memory; middleware protects all app routes.

**Local anon mode** (`MEMORY_OS_ALLOW_ANON=true`): requests without `Authorization` use tenant `demo-tenant` (or `X-Tenant-ID` header). **Never enable in production.**

```bash
# Register
curl -X POST http://localhost:8000/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"you@example.com","password":"secret123","organization_name":"Acme"}'

# Create API key (JWT required)
curl -X POST http://localhost:8000/v1/api-keys \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{"name":"agent-key","scopes":["memory:read","memory:write"]}'
```

See [docs/auth-and-rbac.md](docs/auth-and-rbac.md).

---

## API reference

Interactive docs: http://localhost:8000/docs

### System

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/v1/health` | Liveness |
| `GET` | `/v1/ready` | Readiness + component status |
| `GET` | `/v1/admin/stats` | Admin statistics |
| `GET` | `/metrics` | Prometheus (token required in production) |
| `GET` | `/developer` | Machine-readable portal index |

### Auth

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/v1/auth/register` | Create org + owner user |
| `POST` | `/v1/auth/login` | Issue access + refresh tokens |
| `POST` | `/v1/auth/refresh` | Rotate refresh token |
| `POST` | `/v1/auth/logout` | Revoke refresh session |
| `GET` | `/v1/auth/me` | Current user profile |

### Memory

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/v1/memory` | Create memory (`Idempotency-Key` supported) |
| `GET` | `/v1/memory` | List memories (paginated) |
| `GET` | `/v1/memory/{id}` | Get by ID |
| `PATCH` | `/v1/memory/{id}` | Update fields |
| `DELETE` | `/v1/memory/{id}` | Delete single memory |
| `POST` | `/v1/memory/search` | Hybrid search |
| `POST` | `/v1/memory/extract` | Rule-based extraction |
| `POST` | `/v1/memory/as-of` | Temporal truth at timestamp |
| `GET` | `/v1/memory/{id}/timeline` | Version timeline |
| `GET` | `/v1/memory/{id}/provenance` | Provenance chain |
| `POST` | `/v1/memory/export` | GDPR export |
| `POST` | `/v1/memory/delete` | GDPR cascade delete |
| `POST` | `/v1/context` | Context builder v2 |

### Operations

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/v1/operations/deduplication` | Duplicate clusters |
| `GET` | `/v1/operations/conflicts` | Conflict reports |
| `GET` | `/v1/operations/temporal/as-of` | Temporal query |
| `GET` | `/v1/operations/entity-resolution` | Entity merge candidates |
| `POST` | `/v1/operations/reflection` | Reflection plan |
| `POST` | `/v1/operations/reflection/execute` | Execute reflection actions |

### Sessions, graph, benchmarks

| Method | Path | Description |
|--------|------|-------------|
| `GET/POST` | `/v1/sessions` | Agent sessions |
| `GET/POST` | `/v1/sessions/{id}/events` | Session replay |
| `GET/POST` | `/v1/graph` | Knowledge graph |
| `POST` | `/v1/benchmarks/run` | MemoryBench run |

### Developer, audit, metering

| Method | Path | Description |
|--------|------|-------------|
| `GET/POST/DELETE` | `/v1/api-keys` | API key management |
| `GET/POST/DELETE` | `/v1/webhooks` | Webhook subscriptions |
| `GET` | `/v1/audit/logs` | Append-only audit trail |
| `GET` | `/v1/metering/usage` | 30-day usage counters |
| `GET` | `/v1/analytics/summary` | Analytics rollup |

**Error envelope** (all endpoints):

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Human-readable message",
    "request_id": "req_abc123",
    "details": {}
  }
}
```

---

## Dashboard

Next.js 15 admin UI at http://localhost:3000.

| Route | Purpose |
|-------|---------|
| `/login` | Register / sign in |
| `/dashboard` | Overview + system stats |
| `/memory-explorer` | Browse, search, create memories |
| `/context-builder` | Build agent context bundles |
| `/knowledge-graph` | Graph visualization |
| `/timeline` | Temporal memory timeline |
| `/sessions` | Agent session list |
| `/replay` | Session event replay |
| `/reflection` | Reflection planner + execute |
| `/analytics` | Usage charts |
| `/api-keys` | Create / revoke API keys |
| `/webhooks` | Webhook management |
| `/developer` | API docs + SDK links |
| `/mcp` | MCP setup for Cursor |
| `/system-health` | Component readiness |
| `/settings/security` | Live audit log viewer |
| `/settings/organization` | Org profile |

**Production build:**

```bash
cd dashboard
npm ci
NEXT_PUBLIC_MEMORY_OS_API_URL=https://api.yourdomain.com npm run build
npm start
```

Auth middleware requires login for all `(app)/` routes. Refresh tokens are httpOnly cookies set by `/api/auth/*` routes.

---

## SDKs & CLI

All SDKs are **model-independent** — you supply embeddings; the SDK never generates them.

### Python

```bash
pip install -e packages/sdk-python
```

```python
from memoryos import MemoryOS

client = MemoryOS(api_key="mos_...", base_url="http://localhost:8000")
mem = client.memory.create("User prefers dark mode", idempotency_key="create-001")
results = client.memory.search("dark mode preferences", top_k=5)
ctx = client.context.build("What are the user's UI preferences?")
```

### TypeScript

```bash
cd packages/sdk-typescript && npm install && npm run build
```

```typescript
import { MemoryOS } from "@memory-os/sdk";

const client = new MemoryOS({ apiKey: "mos_...", baseUrl: "http://localhost:8000" });
const mem = await client.memories.create({ content: "User prefers dark mode" });
const results = await client.memories.search({ query: "UI preferences", top_k: 5 });
```

### Go, Java, Kotlin, Rust

See `packages/sdk-go`, `packages/sdk-java`, `packages/sdk-kotlin`, `packages/sdk-rust`.

### CLI

```bash
pip install -e packages/cli
memoryos --help
export MEMORY_OS_API_KEY=mos_...
memoryos memory create "User lives in Dhaka"
memoryos memory search "where does user live"
```

---

## MCP server

Expose MEMORY OS as MCP tools for Cursor, Claude Desktop, and other MCP clients.

```bash
pip install -r mcp/requirements.txt
export MEMORY_OS_API_URL=http://localhost:8000
export MEMORY_OS_API_KEY=mos_your_key_here   # required
python scripts/mcp_stdio_server.py
```

**Docker:**

```bash
docker build -f mcp/Dockerfile -t memory-os-mcp .
docker run -e MEMORY_OS_API_URL=http://api:8000 -e MEMORY_OS_API_KEY=mos_... memory-os-mcp
```

**Tools:** `memory_create`, `memory_search`, `memory_get`, `memory_update`, `memory_delete`, `memory_extract`, `memory_context`, `memory_timeline`, `memory_provenance`, `memory_graph`, `session_create`, `session_events`

See [docs/mcp.md](docs/mcp.md) and the dashboard `/mcp` page for Cursor config.

---

## Testing

### API (pytest)

```bash
cd services/api
pip install -r requirements.txt pytest pytest-asyncio
PYTHONPATH=. python -m pytest -q
# 60 passed, 1 skipped (Postgres RLS — needs TEST_DATABASE_URL)
```

### Dashboard

```bash
cd dashboard
npm run typecheck
npm run lint
npm run build
npm run test:e2e          # Playwright (starts API + dashboard locally)
```

### Load test (k6)

```bash
# Dev (anon mode)
K6_ALLOW_ANON=true k6 run scripts/load/k6-smoke.js

# Production (API key required)
K6_API_URL=https://api.example.com K6_API_KEY=mos_... k6 run scripts/load/k6-smoke.js
```

### CI

GitHub Actions workflows:

| Workflow | Runs |
|----------|------|
| `api-ci.yml` | pytest + Postgres RLS job |
| `dashboard-ci.yml` | typecheck, lint, build, Playwright e2e |
| `sdk-ci.yml` | Python compile, TS build, SDK smoke test |

---

## Production deployment

See [docs/enterprise-deploy.md](docs/enterprise-deploy.md) for the full 18-step checklist.

### 1. Generate secrets

```bash
export JWT_SECRET=$(openssl rand -hex 32)
export API_KEY_PEPPER=$(openssl rand -hex 32)
export METRICS_TOKEN=$(openssl rand -hex 32)
export GRAFANA_ADMIN_PASSWORD=$(openssl rand -hex 16)
export NEXT_PUBLIC_MEMORY_OS_API_URL=https://api.yourdomain.com
```

### 2. Start production stack

```bash
cp .env.example .env
# Edit .env with secrets above
docker compose -f docker-compose.yml -f docker-compose.prod.yml up --build -d
```

Production overlay enforces:

- `MEMORY_OS_ALLOW_ANON=false`
- Required `JWT_SECRET`, `API_KEY_PEPPER`, `METRICS_TOKEN`
- Startup validation rejects weak secrets
- Celery worker + beat
- Prometheus scrape auth (`prometheus.prod.yml`)
- Restart policies + resource limits

### 3. Kubernetes

Manifests under `infra/kubernetes/`:

- `01-config-secrets.yaml` — ConfigMap + Secret template
- `10-api.yaml` — API Deployment + HPA
- `20-worker.yaml` — Celery worker
- `30-dashboard.yaml` — Dashboard Deployment

Configure secrets via your secrets manager before applying.

### Production checklist

1. Strong `JWT_SECRET` and `API_KEY_PEPPER` (≥32 chars)
2. `MEMORY_OS_ALLOW_ANON=false` (default)
3. `METRICS_TOKEN` + Prometheus bearer scrape
4. Postgres with RLS + `alembic upgrade head` (auto via entrypoint)
5. Redis for distributed rate limiting + workers
6. Restrict `CORS_ORIGINS`
7. HTTPS termination at load balancer
8. Run `make test-all` before deploy

---

## Security & compliance

| Feature | Status |
|---------|--------|
| JWT + refresh rotation | ✅ |
| Scoped API keys (hashed at rest) | ✅ |
| RBAC (5 roles) | ✅ |
| PostgreSQL RLS | ✅ (Postgres) |
| Rate limiting | ✅ 120 RPM default |
| Auth endpoint rate limit | ✅ 20/min per IP |
| Append-only audit log | ✅ |
| Webhook SSRF protection | ✅ |
| Webhook secret encryption | ✅ |
| Metrics token auth | ✅ (production) |
| Usage metering | ✅ Counters only (no hard quotas) |
| GDPR export/delete | ⚠️ Partial cross-store cascade |

Full details: [docs/security.md](docs/security.md)

---

## Observability

| Endpoint | Purpose |
|----------|---------|
| `/metrics` | Prometheus (`memoryos_http_requests_total`, latency histograms) |
| `/v1/health` | Liveness probe |
| `/v1/ready` | Readiness — probes Postgres (required), Redis, Neo4j, OpenSearch (optional) |
| `/v1/audit/logs` | Append-only request audit trail |
| `/v1/metering/usage` | 30-day usage by metric |

**Docker stack:** Prometheus `:9090`, Grafana `:3001` (dashboards auto-provisioned).

Optional OpenTelemetry: set `OTEL_ENABLED=true` and `OTEL_EXPORTER_ENDPOINT`.

---

## Documentation

| Doc | Topic |
|-----|-------|
| [docs/architecture.md](docs/architecture.md) | System design |
| [docs/memory-model.md](docs/memory-model.md) | Canonical memory schema |
| [docs/temporal-memory.md](docs/temporal-memory.md) | Temporal truth engine |
| [docs/retrieval.md](docs/retrieval.md) | Hybrid retrieval + ranking |
| [docs/provenance.md](docs/provenance.md) | Provenance chains |
| [docs/auth-and-rbac.md](docs/auth-and-rbac.md) | Auth, roles, scopes |
| [docs/security.md](docs/security.md) | Security controls |
| [docs/enterprise-deploy.md](docs/enterprise-deploy.md) | Production checklist |
| [docs/benchmarks.md](docs/benchmarks.md) | MemoryBench categories |
| [docs/mcp.md](docs/mcp.md) | MCP setup |
| [docs/replay.md](docs/replay.md) | Session replay |
| [docs/production.md](docs/production.md) | Production notes |

---

## Known limitations

These are intentional or in-progress — reported honestly:

- **No LLM inside MEMORY OS** — extraction is rule-based; plug in your model upstream
- **Reflection is explicit** — plans do not auto-apply; call `reflection/execute`
- **GDPR cascade delete** — Postgres, pgvector, keyword index (OpenSearch/BM25), Neo4j refs, graph mirror
- **Monthly usage quotas** — metering counts usage but does not enforce billing limits
- **Some MemoryBench categories** — scaffolded; full validation needs live DB harness
- **Optional stores** — Redis, Neo4j, OpenSearch degrade gracefully when not configured

---

## Contributing

1. Fork and clone the repository
2. Create a feature branch
3. Run `make api-test` and `make typecheck` (or `make test-all`) before opening a PR
4. Follow existing conventions — minimal diffs, no unrelated changes

---

## License

MIT — see [LICENSE](LICENSE).
