"""Idempotency helpers for route handlers."""
from __future__ import annotations

import json
from typing import Any

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import JSONResponse

from app.api.deps import Principal
from app.service_idempotency import body_hash_from_bytes, lookup_idempotent, store_idempotent

IDEMPOTENT_HEADER = "Idempotency-Key"


async def replay_if_idempotent(
    request: Request,
    principal: Principal,
    session: AsyncSession,
) -> dict | list | None:
    key = request.headers.get(IDEMPOTENT_HEADER) or request.headers.get("X-Idempotency-Key")
    if not key:
        return None
    body = await request.body()
    request.state._idem_body = body  # noqa: SLF001
    cached = await lookup_idempotent(
        session,
        tenant_id=principal.tenant_id,
        key=key,
        method=request.method,
        path=request.url.path.rstrip("/"),
        body_hash=body_hash_from_bytes(body),
    )
    if cached is None:
        return None
    return cached.response_body


async def record_idempotent(
    request: Request,
    principal: Principal,
    session: AsyncSession,
    *,
    status_code: int,
    response_body: dict[str, Any] | list[Any],
    body_hash: str | None = None,
) -> None:
    key = request.headers.get(IDEMPOTENT_HEADER) or request.headers.get("X-Idempotency-Key")
    if not key:
        return
    if body_hash is None:
        body = getattr(request.state, "_idem_body", b"")
        body_hash = body_hash_from_bytes(body)
    await store_idempotent(
        session,
        tenant_id=principal.tenant_id,
        key=key,
        method=request.method,
        path=request.url.path.rstrip("/"),
        body_hash=body_hash,
        status_code=status_code,
        response_body=response_body,
    )
