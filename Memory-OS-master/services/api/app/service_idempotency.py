"""HTTP idempotency key storage and lookup."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import IdempotencyKey

TTL_HOURS = 24


def _hash_body(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


async def lookup_idempotent(
    session: AsyncSession,
    *,
    tenant_id: str,
    key: str,
    method: str,
    path: str,
    body_hash: str,
) -> IdempotencyKey | None:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=TTL_HOURS)
    row = (
        await session.execute(
            select(IdempotencyKey).where(
                IdempotencyKey.tenant_id == tenant_id,
                IdempotencyKey.idempotency_key == key,
                IdempotencyKey.method == method,
                IdempotencyKey.path == path,
                IdempotencyKey.created_at >= cutoff,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        return None
    if row.request_hash != body_hash:
        return None  # same key, different body — caller should use a new key
    return row


async def store_idempotent(
    session: AsyncSession,
    *,
    tenant_id: str,
    key: str,
    method: str,
    path: str,
    body_hash: str,
    status_code: int,
    response_body: dict | list | None,
) -> None:
    row = IdempotencyKey(
        tenant_id=tenant_id,
        idempotency_key=key,
        method=method,
        path=path.rstrip("/"),
        request_hash=body_hash,
        status_code=status_code,
        response_body=response_body or {},
    )
    session.add(row)
    await session.commit()


def body_hash_from_bytes(body: bytes) -> str:
    return _hash_body(body)


def body_hash_from_json(data: object) -> str:
    return _hash_body(json.dumps(data, sort_keys=True, separators=(",", ":")).encode())
