"""Idempotent background tasks.

These run against the same database as the API. Each task opens its own async
session. Import paths assume the API package is available on PYTHONPATH (the
worker image installs it as a dependency).

Tasks:
  - run_reflection       advanced consolidation scan (duplicates, stale,
                         missing provenance, conflicts) via consolidation engine
  - rollup_analytics     aggregate analytics_events (no-op if none)
  - deliver_webhook      attempt a single webhook delivery with retry semantics
  - sync_graph           project a memory's entities/relationships into the graph
"""
from __future__ import annotations

import asyncio

from worker.celery_app import celery_app


def _run(coro):
    return asyncio.run(coro)


@celery_app.task(name="worker.tasks.run_reflection", bind=True, max_retries=3)
def run_reflection(self, tenant_id: str | None = None) -> dict:
    return _run(_run_reflection(tenant_id))


@celery_app.task(name="worker.tasks.rollup_analytics")
def rollup_analytics() -> dict:
    return _run(_rollup_analytics())


async def _rollup_analytics() -> dict:
    """Aggregate raw analytics_events into usage_meters hourly windows."""
    from datetime import datetime, timedelta, timezone
    from uuid import uuid4

    from sqlalchemy import func, select

    from app.db.session import SessionFactory
    from app.models import AnalyticsEvent, UsageMeter

    now = datetime.now(timezone.utc)
    window_start = now.replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)
    window_end = window_start + timedelta(hours=1)

    async with SessionFactory() as s:
        rows = (
            await s.execute(
                select(
                    AnalyticsEvent.tenant_id,
                    AnalyticsEvent.kind,
                    func.coalesce(func.sum(AnalyticsEvent.value), 0.0),
                )
                .where(AnalyticsEvent.at >= window_start, AnalyticsEvent.at < window_end)
                .group_by(AnalyticsEvent.tenant_id, AnalyticsEvent.kind)
            )
        ).all()

        upserted = 0
        for tenant_id, kind, quantity in rows:
            metric = f"analytics.{kind}"
            existing = (
                await s.execute(
                    select(UsageMeter).where(
                        UsageMeter.tenant_id == tenant_id,
                        UsageMeter.metric == metric,
                        UsageMeter.window_start == window_start,
                    )
                )
            ).scalar_one_or_none()
            if existing:
                existing.quantity = float(quantity)
                existing.window_end = window_end
            else:
                s.add(
                    UsageMeter(
                        id=str(uuid4()),
                        tenant_id=tenant_id,
                        metric=metric,
                        quantity=float(quantity),
                        window_start=window_start,
                        window_end=window_end,
                        meta={"source": "rollup_analytics"},
                    )
                )
            upserted += 1
        await s.commit()

    return {"status": "ok", "window_start": window_start.isoformat(), "rows": upserted}


@celery_app.task(name="worker.tasks.deliver_webhook", bind=True, max_retries=5, default_retry_delay=30)
def deliver_webhook(self, delivery_id: str, secret_plaintext: str) -> dict:
    return _run(_deliver(delivery_id, secret_plaintext))


@celery_app.task(name="worker.tasks.sync_graph")
def sync_graph(tenant_id: str, edges: list[dict]) -> dict:
    return _run(_sync_graph(tenant_id, edges))


async def _run_reflection(tenant_id: str | None) -> dict:
    from sqlalchemy import select
    from app.db.session import SessionFactory
    from app.models import Memory, MemoryEmbedding
    from app.engine.consolidation import MemorySnapshot, run_reflection

    async with SessionFactory() as s:
        q = select(Memory)
        if tenant_id:
            q = q.where(Memory.tenant_id == tenant_id)
        rows = (await s.execute(q)).scalars().all()
        embed_q = select(MemoryEmbedding)
        if tenant_id:
            embed_q = embed_q.where(MemoryEmbedding.tenant_id == tenant_id)
        embeds = {e.memory_id: e.embedding for e in (await s.execute(embed_q)).scalars().all()}

    report = run_reflection(
        [
            MemorySnapshot(
                m.id, m.content, m.status, m.source, m.created_at, m.last_accessed_at,
                m.valid_from, m.valid_until, embeds.get(m.id),
            )
            for m in rows
        ]
    )
    return {
        "scanned": report.scanned,
        "summary": report.summary,
        "action_count": len(report.actions),
        "top_actions": [
            {"action": a.action, "memory_ids": a.memory_ids, "reason": a.reason, "priority": a.priority}
            for a in report.actions[:20]
        ],
    }


async def _deliver(delivery_id: str, secret_plaintext: str) -> dict:
    from app.db.session import SessionFactory
    from app.engine.webhooks import deliver

    async with SessionFactory() as s:
        await deliver(s, delivery_id, secret_plaintext=secret_plaintext)
    return {"delivery_id": delivery_id}


async def _sync_graph(tenant_id: str, edges: list[dict]) -> dict:
    from app.db.session import SessionFactory
    from app.engine.graphstore import build_graph_store

    store = build_graph_store(SessionFactory)
    for e in edges:
        await store.upsert_edge(
            tenant_id, e["source"], e["target"], e.get("rel_type", "related_to"),
            confidence=e.get("confidence", 0.5), source_memory_id=e.get("source_memory_id"),
        )
    return {"edges": len(edges)}
