"""PostgreSQL RLS session helper.

Sets app.current_tenant for the duration of a request so RLS policies apply
even if application-layer filters are bypassed.
"""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings

settings = get_settings()


async def set_rls_tenant(session: AsyncSession, tenant_id: str) -> None:
    if not settings.postgres_rls_enabled or not settings.is_postgres:
        return
    await session.execute(
        text("SELECT set_config('app.current_tenant', :tid, true)"),
        {"tid": tenant_id},
    )
