"""Celery application for MEMORY OS background workers.

Workers are idempotent. Redis is the broker/result backend. If Redis is not
configured the tasks can still be invoked synchronously in tests via .run().
"""
from __future__ import annotations

import os

from celery import Celery

BROKER = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery("memoryos", broker=BROKER, backend=BROKER)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_default_queue="memoryos",
    beat_schedule={
        "reflection-hourly": {
            "task": "worker.tasks.run_reflection",
            "schedule": 3600.0,
        },
        "analytics-rollup": {
            "task": "worker.tasks.rollup_analytics",
            "schedule": 300.0,
        },
    },
)

import worker.tasks  # noqa: E402,F401  register tasks
