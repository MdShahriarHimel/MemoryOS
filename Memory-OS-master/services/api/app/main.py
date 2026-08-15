"""MEMORY OS API entrypoint.

Model-independent by design: there is no LLM client, no embedding generator, and
no chat endpoint anywhere in this service.
"""
from __future__ import annotations

import secrets
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import Response

from app.api.v1 import analytics as analytics_routes
from app.api.v1 import audit as audit_routes
from app.api.v1 import auth as auth_routes
from app.api.v1 import benchmarks as benchmarks_routes
from app.api.v1 import developer as developer_routes
from app.api.v1 import graph as graph_routes
from app.api.v1 import memory as memory_routes
from app.api.v1 import metering as metering_routes
from app.api.v1 import operations as operations_routes
from app.api.v1 import sessions as sessions_routes
from app.api.v1 import system as system_routes
from app.core.config import get_settings
from app.core.errors import (
    AuthError,
    MemoryOSError,
    memoryos_error_handler,
    unhandled_error_handler,
)
from app.core.startup_checks import validate_production_settings
from app.db.session import dispose_engine, init_db
from app.middleware.audit import AuditMiddleware
from app.middleware.body_limit import BodyLimitMiddleware
from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.usage_meter import UsageMeterMiddleware
from app.telemetry.metrics import metrics_response
from app.telemetry.otel import setup_otel

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    validate_production_settings(settings)
    # Dev convenience: create tables on SQLite. Prod uses Alembic migrations.
    if not settings.is_postgres:
        await init_db()
    yield
    await dispose_engine()


def _custom_openapi(app: FastAPI):
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(
        title="MEMORY OS API",
        version="0.3.0",
        description=(
            "Model-independent cognitive memory infrastructure. "
            "v0.3: temporal truth, extraction, context builder v2, MemoryBench. "
            "See /developer for SDK links, auth guide, and operational endpoints."
        ),
        routes=app.routes,
    )
    schema["info"]["x-logo"] = {"url": "https://memory-os.dev/logo.svg"}
    schema["tags"] = [
        {"name": "memory", "description": "Memory CRUD, search, extraction, context builder, temporal truth"},
        {"name": "benchmarks", "description": "MemoryBench and retrieval evaluation"},
        {"name": "operations", "description": "Deduplication, conflicts, temporal, reflection"},
        {"name": "audit", "description": "Append-only audit trail"},
        {"name": "metering", "description": "Usage counters for billing/quota"},
        {"name": "developer", "description": "API keys, webhooks"},
        {"name": "system", "description": "Health, readiness, metrics"},
    ]
    app.openapi_schema = schema
    return app.openapi_schema


app = FastAPI(
    title="MEMORY OS API",
    version="0.3.0",
    description="Model-independent cognitive memory infrastructure for AI systems.",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)
app.openapi = lambda: _custom_openapi(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID", "X-RateLimit-Limit", "X-RateLimit-Remaining"],
)
app.add_middleware(BodyLimitMiddleware)
app.add_middleware(UsageMeterMiddleware)
app.add_middleware(AuditMiddleware)
app.add_middleware(RateLimitMiddleware)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request.state.request_id = request.headers.get("X-Request-ID") or f"req_{uuid.uuid4().hex[:16]}"
    start = time.perf_counter()
    response = await call_next(request)
    elapsed = time.perf_counter() - start

    if settings.prometheus_enabled:
        try:
            from app.telemetry.metrics import REQUEST_COUNT, REQUEST_LATENCY, _AVAILABLE
            if _AVAILABLE:
                path = request.url.path
                REQUEST_COUNT.labels(request.method, path, str(response.status_code)).inc()
                REQUEST_LATENCY.labels(request.method, path).observe(elapsed)
        except Exception:
            pass

    response.headers["X-Request-ID"] = request.state.request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
    )
    if settings.is_production:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


app.add_exception_handler(MemoryOSError, memoryos_error_handler)
app.add_exception_handler(Exception, unhandled_error_handler)

app.include_router(system_routes.router)
app.include_router(auth_routes.router)
app.include_router(memory_routes.router)
app.include_router(benchmarks_routes.router)
app.include_router(developer_routes.router)
app.include_router(analytics_routes.router)
app.include_router(graph_routes.router)
app.include_router(operations_routes.router)
app.include_router(audit_routes.router)
app.include_router(metering_routes.router)
app.include_router(sessions_routes.router)


def _metrics_authorized(
    *,
    authorization: str | None,
    x_metrics_token: str | None,
) -> bool:
    expected = settings.metrics_token
    if settings.is_production:
        if not expected:
            return False
    elif not expected:
        return True

    provided = None
    if authorization and authorization.lower().startswith("bearer "):
        provided = authorization[7:].strip()
    elif x_metrics_token:
        provided = x_metrics_token.strip()
    return bool(provided and secrets.compare_digest(provided, expected))


@app.get("/metrics")
async def prometheus_metrics(
    authorization: str | None = Header(default=None),
    x_metrics_token: str | None = Header(default=None, alias="X-Metrics-Token"),
):
    if not settings.prometheus_enabled:
        return {"status": "disabled"}
    if not _metrics_authorized(authorization=authorization, x_metrics_token=x_metrics_token):
        raise AuthError("Metrics access denied.")
    body, content_type = metrics_response()
    return Response(content=body, media_type=content_type)


@app.get("/developer")
async def developer_portal() -> dict:
    """Machine-readable developer portal index."""
    return {
        "docs": "/docs",
        "redoc": "/redoc",
        "openapi": "/openapi.json",
        "sdks": {
            "python": "packages/sdk-python",
            "typescript": "packages/sdk-typescript",
            "go": "packages/sdk-go",
            "java": "packages/sdk-java",
            "rust": "packages/sdk-rust",
            "kotlin": "packages/sdk-kotlin",
        },
        "cli": "pip install -e packages/cli",
        "authentication": {"jwt": "/v1/auth/login", "api_key": "/v1/api-keys"},
        "operations": {
            "deduplication": "/v1/operations/deduplication",
            "conflicts": "/v1/operations/conflicts",
            "temporal": "/v1/operations/temporal/as-of",
            "reflection": "/v1/operations/reflection",
            "reflection_execute": "/v1/operations/reflection/execute",
        },
        "v03": {
            "extract": "/v1/memory/extract",
            "as_of": "/v1/memory/as-of",
            "timeline": "/v1/memory/{id}/timeline",
            "provenance": "/v1/memory/{id}/provenance",
            "context": "/v1/context",
            "benchmarks": "/v1/benchmarks/run",
            "sessions": "/v1/sessions",
            "session_replay": "/v1/sessions/{id}/events",
        },
        "observability": {
            "metrics": "/metrics",
            "health": "/v1/health",
            "audit": "/v1/audit/logs",
            "usage": "/v1/metering/usage",
        },
    }


@app.get("/")
async def root() -> dict:
    return {
        "name": settings.app_name,
        "status": "operational",
        "llm": "not-applicable",
        "developer_portal": "/developer",
    }


setup_otel(app)
