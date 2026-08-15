"""Auth / RBAC / API-key / webhook-signing tests.

Run against SQLite + in-memory stores. No external services required.
"""
import os
import uuid

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test_auth.db")
os.environ.setdefault("EMBEDDING_DIM", "4")
os.environ["MEMORY_OS_ALLOW_ANON"] = "false"

import pytest
from httpx import ASGITransport, AsyncClient

from app.db.session import init_db
from app.main import app
from app.security import jwt as jwt_lib
from app.security.passwords import hash_password, verify_password
from app.security.rbac import Role, role_satisfies, scope_satisfies
from app.engine.webhooks import sign


@pytest.fixture(autouse=True, scope="module")
def _db():
    import asyncio
    if os.path.exists("test_auth.db"):
        os.remove("test_auth.db")
    asyncio.run(init_db())
    yield


def test_password_hash_roundtrip():
    h = hash_password("s3cret-password")
    assert verify_password("s3cret-password", h)
    assert not verify_password("wrong", h)


def test_jwt_roundtrip():
    tok = jwt_lib.encode({"sub": "u1", "tenant_id": "t1", "role": "owner"}, ttl_seconds=60)
    payload = jwt_lib.decode(tok)
    assert payload["sub"] == "u1" and payload["role"] == "owner"


def test_rbac_hierarchy():
    assert role_satisfies("owner", Role.viewer)
    assert role_satisfies("admin", Role.developer)
    assert not role_satisfies("viewer", Role.admin)


def test_scope_admin_implies_all():
    assert scope_satisfies(["admin"], "memory:write")
    assert scope_satisfies(["memory:read"], "memory:read")
    assert not scope_satisfies(["memory:read"], "memory:write")


def test_webhook_signature_is_hmac():
    sig = sign("whsec_test", '{"event":"x"}', 1700000000)
    assert sig.startswith("t=1700000000,v1=")


@pytest.mark.asyncio
async def test_register_login_refresh_flow():
    suffix = uuid.uuid4().hex[:8]
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.post("/v1/auth/register", json={
            "email": f"owner-{suffix}@acme.example.com",
            "password": "password123",
            "organization_name": "Acme",
        })
        assert r.status_code == 201, r.text
        tokens = r.json()

        # authenticated /me
        me = await c.get("/v1/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"})
        assert me.status_code == 200
        assert me.json()["role"] == "owner"

        # refresh rotates the token
        rr = await c.post("/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
        assert rr.status_code == 200
        new_tokens = rr.json()
        assert new_tokens["refresh_token"] != tokens["refresh_token"]

        # reuse of the old (now rotated) refresh token is detected
        reuse = await c.post("/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
        assert reuse.status_code == 401


@pytest.mark.asyncio
async def test_anon_blocked_when_disabled(monkeypatch):
    monkeypatch.setenv("MEMORY_OS_ALLOW_ANON", "false")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        # No Authorization header and anon disabled -> 401
        r = await c.get("/v1/memory")
        assert r.status_code == 401


@pytest.mark.asyncio
async def test_api_key_lifecycle_and_tenant_scope():
    suffix = uuid.uuid4().hex[:8]
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        reg = await c.post("/v1/auth/register", json={
            "email": f"dev-{suffix}@beta.example.com",
            "password": "password123",
            "organization_name": "Beta",
        })
        assert reg.status_code == 201, reg.text
        access = reg.json()["access_token"]
        auth = {"Authorization": f"Bearer {access}"}

        created = await c.post("/v1/api-keys", headers=auth, json={
            "name": "ci", "scopes": ["memory:read", "memory:write"],
        })
        assert created.status_code == 201
        secret = created.json()["secret"]
        assert secret.startswith("mos_")

        # Use the API key to write + read a memory
        w = await c.post("/v1/memory", headers={"Authorization": f"Bearer {secret}"},
                         json={"content": "beta memory", "confidence": 0.6})
        assert w.status_code == 201
        lst = await c.get("/v1/memory", headers={"Authorization": f"Bearer {secret}"})
        assert lst.status_code == 200
        assert lst.json()["total"] >= 1


@pytest.mark.asyncio
async def test_api_key_admin_scope_grants_admin_routes():
    suffix = uuid.uuid4().hex[:8]
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        reg = await c.post("/v1/auth/register", json={
            "email": f"admin-{suffix}@acme.example.com",
            "password": "password123",
            "organization_name": "Acme Admin",
        })
        assert reg.status_code == 201
        access = reg.json()["access_token"]

        created = await c.post("/v1/api-keys", headers={"Authorization": f"Bearer {access}"}, json={
            "name": "automation-admin",
            "scopes": ["admin", "memory:read", "memory:write"],
        })
        assert created.status_code == 201
        secret = created.json()["secret"]

        audit = await c.get("/v1/audit/logs", headers={"Authorization": f"Bearer {secret}"})
        assert audit.status_code == 200

        reflection = await c.post(
            "/v1/operations/reflection?stale_days=90",
            headers={"Authorization": f"Bearer {secret}"},
        )
        assert reflection.status_code == 200
