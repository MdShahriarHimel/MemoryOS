"""Session listing and replay API tests."""
from __future__ import annotations

import asyncio
import os

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test_sessions.db")
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
    if os.path.exists("test_sessions.db"):
        os.remove("test_sessions.db")
    asyncio.run(init_db())
    yield


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_session_lifecycle_and_replay(client):
    r = await client.post("/v1/sessions", json={"agent_id": "agent-1"})
    assert r.status_code == 201
    session = r.json()
    sid = session["id"]
    assert session["status"] == "active"
    assert session["event_count"] == 0

    r2 = await client.post(f"/v1/sessions/{sid}/events", json={
        "event_type": "request",
        "detail": "User asked about preferences",
        "latency_ms": 12,
    })
    assert r2.status_code == 201
    ev = r2.json()
    assert ev["seq"] == 1
    assert ev["type"] == "request"
    assert ev["detail"] == "User asked about preferences"
    assert ev["latency_ms"] == 12

    r3 = await client.get(f"/v1/sessions/{sid}/events")
    assert r3.status_code == 200
    replay = r3.json()
    assert replay["session_id"] == sid
    assert len(replay["events"]) == 1
    assert replay["events"][0]["type"] == "request"

    r4 = await client.get("/v1/sessions")
    assert r4.status_code == 200
    page = r4.json()
    assert page["total"] >= 1
    assert any(s["id"] == sid for s in page["items"])


@pytest.mark.asyncio
async def test_memory_ops_record_session_events(client):
    r = await client.post("/v1/sessions", json={})
    sid = r.json()["id"]

    r2 = await client.post("/v1/memory/search", json={
        "query": "user preferences",
        "session_id": sid,
        "top_k": 3,
    })
    assert r2.status_code == 200

    r3 = await client.post("/v1/memory", json={
        "content": "User prefers dark mode",
        "memory_type": "preference",
        "session_id": sid,
    })
    assert r3.status_code == 201

    replay = (await client.get(f"/v1/sessions/{sid}/events")).json()
    types = [e["type"] for e in replay["events"]]
    assert "search" in types
    assert "memory_write" in types
