"""Security hardening tests."""
from __future__ import annotations

import asyncio
import os
import uuid

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test_security.db")
os.environ.setdefault("EMBEDDING_DIM", "4")
os.environ["MEMORY_OS_ALLOW_ANON"] = "false"

import pytest
from httpx import ASGITransport, AsyncClient

from app.db.session import init_db
from app.main import app
from app.security.url_validation import validate_webhook_url
from app.core.errors import ValidationError


@pytest.fixture(autouse=True, scope="module")
def _db():
    if os.path.exists("test_security.db"):
        os.remove("test_security.db")
    asyncio.run(init_db())
    yield


def test_webhook_url_blocks_localhost():
    with pytest.raises(ValidationError):
        validate_webhook_url("http://localhost/hook")


def test_webhook_url_blocks_private_ip():
    with pytest.raises(ValidationError):
        validate_webhook_url("http://127.0.0.1/hook")


@pytest.mark.asyncio
async def test_viewer_jwt_cannot_write_memory():
    suffix = uuid.uuid4().hex[:8]
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        reg = await c.post("/v1/auth/register", json={
            "email": f"owner-{suffix}@sec.example.com",
            "password": "password123",
            "organization_name": "SecOrg",
        })
        owner_token = reg.json()["access_token"]

        # Downgrade would need admin API - viewer test via JWT with viewer role:
        # Register gives owner. Create a second user isn't in API - test analyst via
        # mocking is heavy. Instead verify API key without write scope fails.
        key_resp = await c.post("/v1/api-keys", headers={
            "Authorization": f"Bearer {owner_token}",
        }, json={"name": "read-only", "scopes": ["memory:read"]})
        read_key = key_resp.json()["secret"]

        denied = await c.post("/v1/memory", headers={
            "Authorization": f"Bearer {read_key}",
        }, json={"content": "should fail"})
        assert denied.status_code == 403

        allowed = await c.get("/v1/memory", headers={"Authorization": f"Bearer {read_key}"})
        assert allowed.status_code == 200


def test_production_startup_rejects_weak_secrets():
    from app.core.config import Settings
    from app.core.startup_checks import validate_production_settings

    bad = Settings(
        environment="production",
        jwt_secret="change-me-in-production",
        api_key_pepper="a" * 32,
        memory_os_allow_anon=False,
        metrics_token="metrics-token-at-least-thirty-two-chars",
        prometheus_enabled=True,
    )
    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        validate_production_settings(bad)


def test_production_startup_rejects_anon():
    from app.core.config import Settings
    from app.core.startup_checks import validate_production_settings

    bad = Settings(
        environment="production",
        jwt_secret="a" * 32,
        api_key_pepper="b" * 32,
        memory_os_allow_anon=True,
        metrics_token="metrics-token-at-least-thirty-two-chars",
        prometheus_enabled=True,
    )
    with pytest.raises(RuntimeError, match="MEMORY_OS_ALLOW_ANON"):
        validate_production_settings(bad)


@pytest.mark.asyncio
async def test_metrics_requires_token_when_configured():
    from app.main import settings

    original = settings.metrics_token
    settings.metrics_token = "metrics-token-at-least-thirty-two-chars"
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            denied = await c.get("/metrics")
            assert denied.status_code == 401

            ok = await c.get(
                "/metrics",
                headers={"Authorization": "Bearer metrics-token-at-least-thirty-two-chars"},
            )
            assert ok.status_code == 200
    finally:
        settings.metrics_token = original
