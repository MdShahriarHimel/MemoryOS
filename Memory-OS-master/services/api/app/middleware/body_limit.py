"""Reject oversized request bodies before handlers run."""
from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.core.config import get_settings

settings = get_settings()


class BodyLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method in ("POST", "PUT", "PATCH"):
            raw = request.headers.get("content-length")
            if raw:
                try:
                    if int(raw) > settings.max_request_bytes:
                        return JSONResponse(
                            status_code=413,
                            content={
                                "error": {
                                    "code": "PAYLOAD_TOO_LARGE",
                                    "message": "Request body exceeds size limit.",
                                    "request_id": getattr(request.state, "request_id", None),
                                    "details": {"max_bytes": settings.max_request_bytes},
                                }
                            },
                        )
                except ValueError:
                    pass
        return await call_next(request)
