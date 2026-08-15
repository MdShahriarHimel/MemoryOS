"""Consistent API error envelope.

Every error returned to a client has the shape:

    {"error": {"code", "message", "request_id", "details"}}

Stack traces are never exposed.
"""
from __future__ import annotations

from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse


class MemoryOSError(Exception):
    status_code = 500
    code = "INTERNAL_ERROR"

    def __init__(self, message: str, *, details: dict[str, Any] | None = None):
        self.message = message
        self.details = details or {}
        super().__init__(message)


class NotFoundError(MemoryOSError):
    status_code = 404
    code = "NOT_FOUND"


class ValidationError(MemoryOSError):
    status_code = 422
    code = "VALIDATION_ERROR"


class AuthError(MemoryOSError):
    status_code = 401
    code = "UNAUTHENTICATED"


class ForbiddenError(MemoryOSError):
    status_code = 403
    code = "FORBIDDEN"


class RateLimitError(MemoryOSError):
    status_code = 429
    code = "RATE_LIMITED"


class QuotaExceededError(MemoryOSError):
    status_code = 402
    code = "QUOTA_EXCEEDED"


class EmbeddingRequiredError(ValidationError):
    code = "EMBEDDING_REQUIRED"


def _envelope(request: Request, code: str, message: str, details: dict[str, Any]) -> dict:
    return {
        "error": {
            "code": code,
            "message": message,
            "request_id": getattr(request.state, "request_id", None),
            "details": details,
        }
    }


async def memoryos_error_handler(request: Request, exc: MemoryOSError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=_envelope(request, exc.code, exc.message, exc.details),
    )


async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    try:
        import structlog

        structlog.get_logger("memoryos.api").error(
            "unhandled_exception",
            exc_type=type(exc).__name__,
            request_id=getattr(request.state, "request_id", None),
            path=request.url.path,
        )
    except Exception:
        pass
    return JSONResponse(
        status_code=500,
        content=_envelope(request, "INTERNAL_ERROR", "An unexpected error occurred.", {}),
    )
