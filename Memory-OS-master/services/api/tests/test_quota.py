"""Quota enforcement tests."""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.db.session import init_db
from app.main import app


@pytest.mark.asyncio
async def test_quota_blocks_memory_write(monkeypatch):
    monkeypatch.setenv("MEMORY_OS_ALLOW_ANON", "true")
    from app.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setattr("app.service_metering.settings.quota_enforcement_enabled", True)
    await init_db()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        from app.db.session import SessionFactory
        from app.models import TenantQuota

        async with SessionFactory() as s:
            s.add(TenantQuota(tenant_id="demo-tenant", limits={"memory.write": 0}))
            await s.commit()

        r = await client.post(
            "/v1/memory",
            headers={"X-Tenant-ID": "demo-tenant"},
            json={"content": "Quota test memory"},
        )
        assert r.status_code == 402
        assert r.json()["error"]["code"] == "QUOTA_EXCEEDED"
