"""Usage metering middleware — increments hourly counters per tenant/metric."""
from __future__ import annotations

from datetime import datetime, timezone

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import get_settings

settings = get_settings()

METRIC_MAP = {
    "POST:/v1/memory": "memory.write",
    "POST:/v1/memory/search": "memory.search",
    "POST:/v1/context/build": "context.build",
}


class UsageMeterMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)

        if not settings.usage_metering_enabled:
            return response

        tenant_id = getattr(request.state, "tenant_id", None)
        if tenant_id is None:
            return response

        route_key = f"{request.method}:{request.url.path.rstrip('/')}"
        metric = METRIC_MAP.get(route_key)
        if metric is None:
            if request.url.path.startswith("/v1/"):
                metric = "api.request"
            else:
                return response

        try:
            from app.service_metering import increment_usage
            from app.db.session import SessionFactory

            async with SessionFactory() as session:
                await increment_usage(session, tenant_id=tenant_id, metric=metric, quantity=1.0)
                await session.commit()
        except Exception:
            pass

        return response
