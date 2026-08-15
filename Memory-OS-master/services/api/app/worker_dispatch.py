"""Optional Celery task dispatch from the API process."""
from __future__ import annotations

import os


def dispatch_webhook_delivery(delivery_id: str, secret: str = "") -> bool:
    """Enqueue webhook delivery to Celery when REDIS_URL and worker are available."""
    if not os.environ.get("REDIS_URL"):
        return False
    try:
        from worker.tasks import deliver_webhook

        deliver_webhook.delay(delivery_id, secret)
        return True
    except Exception:
        return False


def dispatch_reflection(tenant_id: str | None = None) -> bool:
    if not os.environ.get("REDIS_URL"):
        return False
    try:
        from worker.tasks import run_reflection

        run_reflection.delay(tenant_id)
        return True
    except Exception:
        return False


def dispatch_sync_graph(tenant_id: str, edges: list[dict]) -> bool:
    if not os.environ.get("REDIS_URL"):
        return False
    try:
        from worker.tasks import sync_graph

        sync_graph.delay(tenant_id, edges)
        return True
    except Exception:
        return False
