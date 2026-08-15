"""Integration tests for v0.3 API endpoints."""
from __future__ import annotations

import asyncio
import os

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test_v03.db")
os.environ.setdefault("EMBEDDING_DIM", "4")
os.environ.setdefault("MEMORY_OS_ALLOW_ANON", "true")

import pytest
from httpx import ASGITransport, AsyncClient

from app.db.session import init_db
from app.main import app


@pytest.fixture(autouse=True)
def _allow_anon(monkeypatch):
    monkeypatch.setenv("MEMORY_OS_ALLOW_ANON", "true")


@pytest.fixture(autouse=True, scope="module")
def _db():
    if os.path.exists("test_v03.db"):
        os.remove("test_v03.db")
    asyncio.run(init_db())
    yield


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_extract_endpoint(client):
    r = await client.post("/v1/memory/extract", json={
        "content": "User works at Company A",
        "source": {"type": "conversation", "id": "conv_1"},
    })
    assert r.status_code == 200
    data = r.json()
    assert len(data["facts"]) >= 1
    assert data["method"] in ("rules", "hybrid", "structured")


@pytest.mark.asyncio
async def test_create_with_canonical_fields(client):
    r = await client.post("/v1/memory", json={
        "content": "User lives in Sylhet",
        "memory_type": "fact",
        "subject": "user",
        "predicate": "lives_in",
        "object_value": "Sylhet",
        "confidence": 0.9,
    })
    assert r.status_code == 201
    data = r.json()
    assert data["subject"] == "user"
    assert data["predicate"] == "lives_in"
    assert data["object_value"] == "Sylhet"
    mem_id = data["id"]

    # Provenance
    r2 = await client.get(f"/v1/memory/{mem_id}/provenance")
    assert r2.status_code == 200
    assert r2.json()["memory_id"] == mem_id

    # Timeline
    r3 = await client.get(f"/v1/memory/{mem_id}/timeline")
    assert r3.status_code == 200
    assert len(r3.json()["chain"]) >= 1


@pytest.mark.asyncio
async def test_supersede_chain(client):
    r1 = await client.post("/v1/memory", json={
        "content": "User lives in Sylhet",
        "memory_type": "fact",
        "subject": "user", "predicate": "lives_in", "object_value": "Sylhet",
        "observed_at": "2024-01-01T00:00:00Z",
        "valid_from": "2024-01-01T00:00:00Z",
    })
    id1 = r1.json()["id"]

    r2 = await client.post("/v1/memory", json={
        "content": "User moved to Dhaka",
        "memory_type": "fact",
        "subject": "user", "predicate": "lives_in", "object_value": "Dhaka",
        "supersedes": [id1],
        "observed_at": "2025-01-01T00:00:00Z",
        "valid_from": "2025-01-01T00:00:00Z",
    })
    assert r2.status_code == 201

    r3 = await client.post("/v1/memory/as-of", json={
        "as_of": "2025-06-01T00:00:00Z",
        "subject": "user",
        "predicate": "lives_in",
    })
    assert r3.status_code == 200
    truths = r3.json()["truths"]
    assert any(t["current_value"] == "Dhaka" for t in truths)

    # Current truth should be Dhaka (only two memories, second supersedes first)
    r4 = await client.post("/v1/memory/as-of", json={
        "as_of": "2026-06-01T00:00:00Z",
        "subject": "user",
        "predicate": "lives_in",
    })
    truths_now = r4.json()["truths"]
    assert any(t["current_value"] == "Dhaka" for t in truths_now)


@pytest.mark.asyncio
async def test_context_builder_v2(client):
    await client.post("/v1/memory", json={
        "content": "User prefers Python for backend development",
        "memory_type": "preference",
        "subject": "user", "predicate": "prefers", "object_value": "Python",
    })
    r = await client.post("/v1/context", json={"query": "Python backend"})
    assert r.status_code == 200
    data = r.json()
    assert "memories" in data
    assert "current_truths" in data
    assert "provenance" in data
    assert data["query"] == "Python backend"


@pytest.mark.asyncio
async def test_benchmark_run(client):
    r = await client.post("/v1/benchmarks/run", json={"name": "test-run", "scale": 1000})
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "completed"
    assert "total_passed" in data["results"]


@pytest.mark.asyncio
async def test_export_and_delete(client):
    await client.post("/v1/memory", json={"content": "temp memory", "user_id": "u1"})
    r = await client.post("/v1/memory/export", json={"user_id": "u1"})
    assert r.status_code == 200
    assert r.json()["count"] >= 1

    r2 = await client.post("/v1/memory/delete", json={"user_id": "u1", "verify": True})
    assert r2.status_code == 200
    assert r2.json()["deleted_count"] >= 1
