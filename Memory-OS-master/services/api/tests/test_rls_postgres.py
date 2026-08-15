"""PostgreSQL RLS integration tests — skipped unless TEST_DATABASE_URL is set."""
from __future__ import annotations

import os

import pytest

PG_URL = os.environ.get("TEST_DATABASE_URL", "")

pytestmark = pytest.mark.skipif(
    not PG_URL.startswith("postgresql"),
    reason="Set TEST_DATABASE_URL=postgresql+asyncpg://... to run RLS tests",
)


@pytest.mark.asyncio
async def test_rls_blocks_cross_tenant_select():
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

    engine = create_async_engine(PG_URL)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    async with Session() as session:
        await session.execute(text("SELECT set_config('app.current_tenant', 'tenant-a', true)"))
        result = await session.execute(
            text("SELECT COUNT(*) FROM memories WHERE tenant_id = 'tenant-b'")
        )
        count = result.scalar_one()
        assert count == 0, "RLS should block cross-tenant reads"

    await engine.dispose()
