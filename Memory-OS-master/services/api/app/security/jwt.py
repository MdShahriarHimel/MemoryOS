"""Minimal, dependency-free HS256 JWT.

Implemented against the standard library so the service runs and is testable
offline. Supports exp/iat/nbf validation with constant-time signature checks.
For production you may swap in PyJWT — the interface is intentionally small.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Any

from app.core.config import get_settings
from app.core.errors import AuthError


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def encode(payload: dict[str, Any], *, ttl_seconds: int) -> str:
    settings = get_settings()
    now = int(time.time())
    body = {**payload, "iat": now, "nbf": now, "exp": now + ttl_seconds}
    header = {"alg": "HS256", "typ": "JWT"}
    segments = [
        _b64url_encode(json.dumps(header, separators=(",", ":")).encode()),
        _b64url_encode(json.dumps(body, separators=(",", ":")).encode()),
    ]
    signing_input = ".".join(segments).encode()
    signature = hmac.new(settings.jwt_secret.encode(), signing_input, hashlib.sha256).digest()
    segments.append(_b64url_encode(signature))
    return ".".join(segments)


def decode(token: str) -> dict[str, Any]:
    settings = get_settings()
    try:
        header_b64, payload_b64, sig_b64 = token.split(".")
    except ValueError:
        raise AuthError("Malformed token.")

    signing_input = f"{header_b64}.{payload_b64}".encode()
    expected = hmac.new(settings.jwt_secret.encode(), signing_input, hashlib.sha256).digest()
    if not hmac.compare_digest(expected, _b64url_decode(sig_b64)):
        raise AuthError("Invalid token signature.")

    payload = json.loads(_b64url_decode(payload_b64))
    now = int(time.time())
    if payload.get("exp", 0) < now:
        raise AuthError("Token expired.")
    if payload.get("nbf", 0) > now:
        raise AuthError("Token not yet valid.")
    return payload
