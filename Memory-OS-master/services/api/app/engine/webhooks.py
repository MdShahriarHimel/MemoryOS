"""Webhook signing and delivery.

Each payload is signed with HMAC-SHA256 over `{timestamp}.{body}` using the
webhook's secret, sent as the `X-MemoryOS-Signature` header (Stripe-style). The
delivery function is idempotent per WebhookDelivery row and records attempts,
response status, and latency for the delivery-history UI.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time
from datetime import datetime, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Webhook, WebhookDelivery

MAX_ATTEMPTS = 5


def sign(secret: str, body: str, timestamp: int) -> str:
    mac = hmac.new(secret.encode(), f"{timestamp}.{body}".encode(), hashlib.sha256)
    return f"t={timestamp},v1={mac.hexdigest()}"


async def enqueue(session: AsyncSession, tenant_id: str, event: str, payload: dict) -> list[str]:
    """Create WebhookDelivery rows for every subscribed webhook. Returns ids."""
    hooks = (
        await session.execute(
            select(Webhook).where(Webhook.tenant_id == tenant_id, Webhook.status == "active")
        )
    ).scalars().all()
    ids: list[str] = []
    pending: list[tuple[str, str]] = []
    for h in hooks:
        if event in (h.events or []) or not h.events:
            d = WebhookDelivery(webhook_id=h.id, tenant_id=tenant_id, event=event, payload=payload)
            session.add(d)
            await session.flush()
            ids.append(d.id)
            secret = ""
            if h.secret_enc:
                from app.security.secret_box import decrypt_secret
                secret = decrypt_secret(h.secret_enc)
            pending.append((d.id, secret))
    await session.commit()
    for delivery_id, secret in pending:
        try:
            from app.worker_dispatch import dispatch_webhook_delivery
            dispatch_webhook_delivery(delivery_id, secret)
        except Exception:
            pass
    return ids


async def deliver(session: AsyncSession, delivery_id: str, *, secret_plaintext: str | None = None) -> None:
    """Attempt a single delivery. Safe to retry (idempotent by delivery row)."""
    d = (
        await session.execute(select(WebhookDelivery).where(WebhookDelivery.id == delivery_id))
    ).scalar_one_or_none()
    if d is None or d.status == "delivered":
        return
    hook = (
        await session.execute(select(Webhook).where(Webhook.id == d.webhook_id))
    ).scalar_one_or_none()
    if hook is None:
        return

    secret = secret_plaintext or ""
    if not secret and hook.secret_enc:
        from app.security.secret_box import decrypt_secret
        secret = decrypt_secret(hook.secret_enc)

    body = json.dumps({"event": d.event, "data": d.payload}, separators=(",", ":"))
    ts = int(time.time())
    signature = sign(secret, body, ts)

    d.attempts += 1
    started = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                hook.url,
                content=body,
                headers={
                    "Content-Type": "application/json",
                    "X-MemoryOS-Signature": signature,
                    "X-MemoryOS-Event": d.event,
                },
            )
        d.response_status = resp.status_code
        d.latency_ms = int((time.perf_counter() - started) * 1000)
        if 200 <= resp.status_code < 300:
            d.status = "delivered"
            d.delivered_at = datetime.now(timezone.utc)
        else:
            d.status = "failed" if d.attempts >= MAX_ATTEMPTS else "pending"
            d.error = f"HTTP {resp.status_code}"
    except Exception as exc:  # noqa: BLE001
        d.latency_ms = int((time.perf_counter() - started) * 1000)
        d.status = "failed" if d.attempts >= MAX_ATTEMPTS else "pending"
        d.error = str(exc)[:500]
    await session.commit()
