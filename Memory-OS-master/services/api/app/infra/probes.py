"""Dependency health probes for readiness checks."""
from __future__ import annotations

import httpx

from app.core.config import Settings


async def probe_redis(url: str) -> str:
    try:
        import redis.asyncio as aioredis

        client = aioredis.from_url(url, decode_responses=True)
        await client.ping()
        await client.aclose()
        return "operational"
    except Exception:
        return "unavailable"


async def probe_neo4j(uri: str, user: str, password: str) -> str:
    try:
        from neo4j import AsyncGraphDatabase

        driver = AsyncGraphDatabase.driver(uri, auth=(user, password))
        async with driver.session() as session:
            await session.run("RETURN 1")
        await driver.close()
        return "operational"
    except Exception:
        return "unavailable"


async def probe_opensearch(url: str) -> str:
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get(f"{url.rstrip('/')}/_cluster/health")
            if r.status_code == 200:
                return "operational"
    except Exception:
        pass
    return "unavailable"


async def component_status(settings: Settings) -> dict[str, str]:
    out: dict[str, str] = {}
    if settings.redis_url:
        out["redis"] = await probe_redis(settings.redis_url)
    else:
        out["redis"] = "not_configured"

    if settings.neo4j_uri:
        out["neo4j"] = await probe_neo4j(
            settings.neo4j_uri, settings.neo4j_username, settings.neo4j_password
        )
    else:
        out["neo4j"] = "not_configured"

    if settings.opensearch_url:
        out["opensearch"] = await probe_opensearch(settings.opensearch_url)
    else:
        out["opensearch"] = "not_configured"
    return out
