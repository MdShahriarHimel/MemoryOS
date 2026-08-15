"""Append-only audit logging middleware.

Records mutating API calls (POST/PUT/PATCH/DELETE) to audit_logs. Read paths are
not logged by default to keep volume manageable; enable via AUDIT_READS env if
needed.
"""
from __future__ import annotations

import os

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import get_settings

settings = get_settings()
AUDIT_READS = os.environ.get("MEMORY_OS_AUDIT_READS", "false").lower() == "true"


class AuditMiddleware(BaseHTTPMiddleware):
    MUTATING = {"POST", "PUT", "PATCH", "DELETE"}

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)

        method = request.method.upper()
        if method not in self.MUTATING and not AUDIT_READS:
            return response

        if request.url.path.startswith(("/docs", "/openapi", "/metrics", "/v1/health")):
            return response

        tenant_id = getattr(request.state, "tenant_id", None)
        actor = getattr(request.state, "actor", None)
        if tenant_id is None:
            return response

        try:
            from app.service_audit import record_audit
            from app.db.session import SessionFactory

            async with SessionFactory() as session:
                await record_audit(
                    session,
                    tenant_id=tenant_id,
                    actor=actor,
                    action=f"{method} {request.url.path}",
                    target=request.url.path,
                    request_id=getattr(request.state, "request_id", None),
                    result="ok" if response.status_code < 400 else "error",
                    details={"status_code": response.status_code},
                )
                await session.commit()
        except Exception:
            pass  # audit must never break the request path

        return response
