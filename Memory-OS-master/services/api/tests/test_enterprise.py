"""Enterprise integration tests — API coverage, isolation, temporal, ops."""
from __future__ import annotations

import asyncio
import os
import uuid

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test_enterprise.db")
os.environ.setdefault("EMBEDDING_DIM", "4")
os.environ["MEMORY_OS_ALLOW_ANON"] = "true"

import pytest
from httpx import ASGITransport, AsyncClient

from app.db.session import init_db
from app.main import app


@pytest.fixture(autouse=True)
def _allow_anon(monkeypatch):
    monkeypatch.setenv("MEMORY_OS_ALLOW_ANON", "true")


@pytest.fixture(autouse=True, scope="module")
def _db():
    if os.path.exists("test_enterprise.db"):
        os.remove("test_enterprise.db")
    asyncio.run(init_db())
    yield


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


TENANT_A = "tenant-alpha"
TENANT_B = "tenant-beta"


@pytest.mark.asyncio
async def test_system_endpoints(client):
    assert (await client.get("/v1/health")).status_code == 200
    ready = await client.get("/v1/ready")
    assert ready.status_code == 200
    assert (await client.get("/developer")).status_code == 200


@pytest.mark.asyncio
async def test_tenant_isolation_cross_tenant(client):
    ha = {"X-Tenant-ID": TENANT_A}
    hb = {"X-Tenant-ID": TENANT_B}

    ca = await client.post("/v1/memory", headers=ha, json={"content": "Alpha secret memory"})
    assert ca.status_code == 201
    mem_a = ca.json()["id"]

    cb = await client.post("/v1/memory", headers=hb, json={"content": "Beta secret memory"})
    assert cb.status_code == 201

    get_b = await client.get(f"/v1/memory/{mem_a}", headers=hb)
    assert get_b.status_code == 404

    list_a = await client.get("/v1/memory", headers=ha)
    assert list_a.json()["total"] >= 1
    list_b = await client.get("/v1/memory", headers=hb)
    assert all(m["content"] != "Alpha secret memory" for m in list_b.json()["items"])


@pytest.mark.asyncio
async def test_temporal_truth_api(client):
    r1 = await client.post("/v1/memory", json={
        "content": "User lives in Sylhet",
        "subject": "user", "predicate": "lives_in", "object_value": "Sylhet",
    })
    assert r1.status_code == 201
    id1 = r1.json()["id"]

    r2 = await client.post("/v1/memory", json={
        "content": "User moved to Dhaka",
        "subject": "user", "predicate": "lives_in", "object_value": "Dhaka",
        "supersedes": [id1],
    })
    assert r2.status_code == 201

    as_of = await client.post("/v1/memory/as-of", json={
        "as_of": "2025-06-01T00:00:00Z",
        "subject": "user", "predicate": "lives_in",
    })
    assert as_of.status_code == 200

    timeline = await client.get(f"/v1/memory/{id1}/timeline")
    assert timeline.status_code == 200
    assert len(timeline.json()["chain"]) >= 1


@pytest.mark.asyncio
async def test_operations_conflicts_and_dedup(client):
    await client.post("/v1/memory", json={"content": "User likes spicy food"})
    await client.post("/v1/memory", json={"content": "User doesn't like spicy food anymore"})

    conflicts = await client.get("/v1/operations/conflicts")
    assert conflicts.status_code == 200

    await client.post("/v1/memory", json={"content": "User prefers dark mode"})
    await client.post("/v1/memory", json={"content": "User prefers dark mode"})

    dupes = await client.get("/v1/operations/deduplication")
    assert dupes.status_code == 200
    assert isinstance(dupes.json(), list)


@pytest.mark.asyncio
async def test_entity_resolution_endpoint(client):
    await client.post("/v1/memory", json={
        "content": "Bob called", "subject": "Bob", "predicate": "name", "object_value": "Bob",
    })
    await client.post("/v1/memory", json={
        "content": "Robert emailed", "subject": "Robert", "predicate": "name", "object_value": "Robert",
    })
    r = await client.get("/v1/operations/entity-resolution")
    assert r.status_code == 200
    assert "merge_groups" in r.json()


@pytest.mark.asyncio
async def test_idempotency_create(client):
    key = f"idem-{uuid.uuid4().hex}"
    headers = {"Idempotency-Key": key}
    body = {"content": "Idempotent memory test"}
    r1 = await client.post("/v1/memory", headers=headers, json=body)
    r2 = await client.post("/v1/memory", headers=headers, json=body)
    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["id"] == r2.json()["id"]


@pytest.mark.asyncio
async def test_delete_cascade_stores(client):
    r = await client.post("/v1/memory", json={"content": "To be deleted"})
    assert r.status_code == 201
    d = await client.post("/v1/memory/delete", json={"verify": True})
    assert d.status_code == 200
    data = d.json()
    assert data["deleted_count"] >= 1
    assert "postgres" in data["stores_cleaned"]


@pytest.mark.asyncio
async def test_search_explanation_summary(client):
    await client.post("/v1/memory", json={"content": "User loves hiking in the mountains"})
    s = await client.post("/v1/memory/search", json={"query": "hiking mountains", "top_k": 5})
    assert s.status_code == 200
    results = s.json()["results"]
    if results:
        assert "explanation_summary" in results[0]
        assert len(results[0]["explanation_summary"]) > 0


@pytest.mark.asyncio
async def test_full_api_smoke(client):
    """Smoke every major route group."""
    routes = [
        ("GET", "/v1/memory"),
        ("GET", "/v1/sessions"),
        ("GET", "/v1/operations/deduplication"),
        ("GET", "/v1/operations/conflicts"),
        ("GET", "/v1/operations/entity-resolution"),
        ("GET", "/v1/metering/usage"),
        ("GET", "/v1/analytics/summary"),
        ("GET", "/v1/graph"),
        ("GET", "/v1/benchmarks"),
        ("GET", "/v1/admin/stats"),
        ("GET", "/v1/audit/logs"),
    ]
    for method, path in routes:
        r = await client.request(method, path)
        assert r.status_code in (200, 403, 401), f"{method} {path} -> {r.status_code}: {r.text[:200]}"

    bench = await client.post("/v1/benchmarks/run", json={"name": "enterprise-smoke", "scale": 100})
    assert bench.status_code == 200
    assert bench.json()["status"] == "completed"
