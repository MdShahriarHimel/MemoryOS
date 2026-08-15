"""Sliding-window rate limiter per tenant.

Uses Redis when REDIS_URL is configured; falls back to an in-process counter
for zero-dependency dev/test runs.
"""
from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import get_settings

settings = get_settings()


@dataclass
class _Bucket:
    count: int = 0
    window_start: float = field(default_factory=time.time)


class InMemoryLimiter:
    def __init__(self) -> None:
        self._buckets: dict[str, _Bucket] = defaultdict(_Bucket)

    def check(self, key: str, *, limit: int, window_sec: int = 60) -> tuple[bool, int]:
        now = time.time()
        b = self._buckets[key]
        if now - b.window_start >= window_sec:
            b.count = 0
            b.window_start = now
        b.count += 1
        remaining = max(limit - b.count, 0)
        return b.count <= limit, remaining


_memory = InMemoryLimiter()


async def _redis_check(key: str, *, limit: int, window_sec: int = 60) -> tuple[bool, int]:
    try:
        import redis.asyncio as aioredis  # type: ignore
    except ImportError:
        return _memory.check(key, limit=limit, window_sec=window_sec)

    if not settings.redis_url:
        return _memory.check(key, limit=limit, window_sec=window_sec)

    client = aioredis.from_url(settings.redis_url, decode_responses=True)
    try:
        pipe = client.pipeline()
        pipe.incr(key)
        pipe.expire(key, window_sec)
        count, _ = await pipe.execute()
        remaining = max(limit - int(count), 0)
        return int(count) <= limit, remaining
    finally:
        await client.aclose()


class RateLimitMiddleware(BaseHTTPMiddleware):
    SKIP_PATHS = {"/v1/health", "/v1/ready", "/metrics", "/docs", "/openapi.json", "/"}
    AUTH_PATHS = {"/v1/auth/login", "/v1/auth/register"}
    AUTH_LIMIT_RPM = 20

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path.rstrip("/")
        if not settings.rate_limit_enabled or path in self.SKIP_PATHS:
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        if path in self.AUTH_PATHS:
            key = f"rl:auth:{client_ip}:{int(time.time()) // 60}"
            limit = self.AUTH_LIMIT_RPM
        else:
            tenant = request.headers.get("X-Tenant-ID", "anon")
            auth = request.headers.get("Authorization", "")
            if auth:
                tenant = f"auth:{hash(auth) & 0xFFFF_FFFF:x}"
            key = f"rl:{tenant}:{int(time.time()) // 60}"
            limit = settings.rate_limit_rpm + settings.rate_limit_burst

        allowed, remaining = await _redis_check(key, limit=limit)

        if not allowed:
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=429,
                content={
                    "error": {
                        "code": "RATE_LIMITED",
                        "message": "Rate limit exceeded.",
                        "details": {"limit_rpm": settings.rate_limit_rpm, "retry_after_sec": 60},
                    }
                },
                headers={
                    "X-RateLimit-Limit": str(settings.rate_limit_rpm),
                    "X-RateLimit-Remaining": "0",
                    "Retry-After": "60",
                },
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(settings.rate_limit_rpm)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response
