"""OpenTelemetry instrumentation (optional).

When OTEL_ENABLED=true and OTEL_EXPORTER_ENDPOINT is set, configures tracing
for FastAPI, SQLAlchemy, and httpx. No-op otherwise.
"""
from __future__ import annotations

from app.core.config import get_settings

settings = get_settings()


def setup_otel(app) -> None:
    if not settings.otel_enabled:
        return

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError:
        return

    resource = Resource.create({"service.name": settings.otel_service_name})
    provider = TracerProvider(resource=resource)

    if settings.otel_exporter_endpoint:
        exporter = OTLPSpanExporter(endpoint=settings.otel_exporter_endpoint, insecure=True)
        provider.add_span_processor(BatchSpanProcessor(exporter))

    trace.set_tracer_provider(provider)
    FastAPIInstrumentor.instrument_app(app)

    try:
        from app.db.session import engine
        SQLAlchemyInstrumentor().instrument(engine=engine.sync_engine if hasattr(engine, "sync_engine") else engine)
    except Exception:
        pass
