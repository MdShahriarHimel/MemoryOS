"""Application configuration.

All settings are environment-driven. No secrets are hardcoded. MEMORY OS is
model-independent: there is deliberately no LLM/embedding provider config here.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "MEMORY OS"
    environment: str = Field(default="development")

    # Postgres is the source of truth. Falls back to SQLite for zero-dependency
    # local runs so the core engine is testable without Docker.
    database_url: str = Field(default="sqlite+aiosqlite:///./memory_os.db")

    redis_url: str | None = Field(default=None)
    neo4j_uri: str | None = Field(default=None)
    neo4j_username: str = Field(default="neo4j")
    neo4j_password: str = Field(default="memoryos-graph")
    opensearch_url: str | None = Field(default=None)

    db_pool_size: int = Field(default=10)
    db_max_overflow: int = Field(default=20)
    db_pool_recycle: int = Field(default=1800)

    # Vector dimension the deployment expects. Clients must supply embeddings of
    # this length. MEMORY OS never generates embeddings.
    embedding_dim: int = Field(default=1536)

    jwt_secret: str = Field(default="change-me-in-production")
    jwt_algorithm: str = "HS256"
    access_token_ttl_seconds: int = 3600
    refresh_token_ttl_seconds: int = 60 * 60 * 24 * 14

    # Pepper mixed into API-key hashes at rest.
    api_key_pepper: str = Field(default="change-me-pepper")

    # Anonymous local access (X-Tenant-ID without Authorization). Off by default.
    memory_os_allow_anon: bool = Field(default=False)

    # Bearer or X-Metrics-Token for /metrics when set; required in production.
    metrics_token: str | None = Field(default=None)

    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://127.0.0.1:3000"]
    )

    max_request_bytes: int = 1_000_000
    default_page_size: int = 25
    max_page_size: int = 200

    # ---- Rate limiting -----------------------------------------------------
    rate_limit_enabled: bool = Field(default=True)
    rate_limit_rpm: int = Field(default=120)  # requests per minute per tenant
    rate_limit_burst: int = Field(default=20)

    # ---- OpenTelemetry -----------------------------------------------------
    otel_enabled: bool = Field(default=False)
    otel_service_name: str = Field(default="memory-os-api")
    otel_exporter_endpoint: str | None = Field(default=None)  # e.g. http://localhost:4317

    # ---- Prometheus --------------------------------------------------------
    prometheus_enabled: bool = Field(default=True)

    # ---- Object storage (S3-compatible) ------------------------------------
    object_storage_backend: str = Field(default="local")  # local | s3
    s3_bucket: str | None = Field(default=None)
    s3_endpoint: str | None = Field(default=None)
    s3_region: str = Field(default="us-east-1")
    aws_access_key_id: str | None = Field(default=None)
    aws_secret_access_key: str | None = Field(default=None)
    object_storage_local_path: str = Field(default="./storage")

    # ---- PostgreSQL RLS ----------------------------------------------------
    postgres_rls_enabled: bool = Field(default=True)

    # ---- Usage metering ----------------------------------------------------
    usage_metering_enabled: bool = Field(default=True)
    quota_enforcement_enabled: bool = Field(default=False)
    default_monthly_memory_writes: float = Field(default=1_000_000)
    default_monthly_memory_searches: float = Field(default=5_000_000)
    default_monthly_context_builds: float = Field(default=500_000)

    @property
    def is_postgres(self) -> bool:
        return self.database_url.startswith("postgresql")

    @property
    def is_production(self) -> bool:
        return self.environment.lower() in ("production", "prod")


@lru_cache
def get_settings() -> Settings:
    return Settings()
