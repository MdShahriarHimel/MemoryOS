"""Fail fast when production is misconfigured."""
from __future__ import annotations

from app.core.config import Settings

_WEAK_SECRETS = frozenset({
    "change-me-in-production",
    "change-me-pepper",
    "dev-secret",
    "dev-pepper",
    "secret",
    "password",
    "changeme",
})


def _is_weak_secret(value: str) -> bool:
    normalized = value.strip().lower()
    return not normalized or normalized in _WEAK_SECRETS or len(value) < 32


def validate_production_settings(settings: Settings) -> None:
    if not settings.is_production:
        return

    errors: list[str] = []

    if settings.memory_os_allow_anon:
        errors.append("MEMORY_OS_ALLOW_ANON must be false in production.")

    if _is_weak_secret(settings.jwt_secret):
        errors.append("JWT_SECRET must be at least 32 characters and not a known default.")

    if _is_weak_secret(settings.api_key_pepper):
        errors.append("API_KEY_PEPPER must be at least 32 characters and not a known default.")

    if settings.prometheus_enabled and not settings.metrics_token:
        errors.append("METRICS_TOKEN is required when PROMETHEUS_ENABLED=true in production.")

    if errors:
        raise RuntimeError("Production configuration invalid:\n- " + "\n- ".join(errors))
