"""Reflection plan and execution tests."""
from __future__ import annotations

import asyncio
import os
import uuid

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test_reflection.db")
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
    if os.path.exists("test_reflection.db"):
        os.remove("test_reflection.db")
    asyncio.run(init_db())
    yield


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_reflection_plan(client):
    await client.post("/v1/memory", json={"content": "User likes coffee", "memory_type": "preference"})
    await client.post("/v1/memory", json={"content": "User likes coffee", "memory_type": "preference"})

    r = await client.post("/v1/operations/reflection?stale_days=90")
    assert r.status_code == 200
    data = r.json()
    assert data["scanned"] >= 2
    assert "merge" in data["summary"]


@pytest.mark.asyncio
async def test_reflection_execute_dry_run_and_apply(client):
    content = f"Duplicate fact {uuid.uuid4().hex[:8]}"
    await client.post("/v1/memory", json={"content": content, "memory_type": "fact"})
    await client.post("/v1/memory", json={"content": content, "memory_type": "fact"})

    dry = await client.post("/v1/operations/reflection/execute", json={"dry_run": True})
    assert dry.status_code == 200
    assert dry.json()["dry_run"] is True
    assert any(r["result"] == "dry_run" for r in dry.json()["results"])

    applied = await client.post("/v1/operations/reflection/execute", json={
        "dry_run": False,
        "action_types": ["merge"],
    })
    assert applied.status_code == 200
    assert applied.json()["dry_run"] is False
    assert any(r["result"] == "applied" for r in applied.json()["results"])
