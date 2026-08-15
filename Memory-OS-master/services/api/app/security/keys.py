"""API key generation and hashing.

Raw secret keys are shown exactly once at creation. Only a peppered SHA-256 hash
is stored. Lookups compare hashes. Never log raw keys.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets

from app.core.config import get_settings

PREFIX = "mos"


def generate_api_key() -> tuple[str, str, str]:
    """Return (full_key, prefix, key_hash). full_key is shown once."""
    body = secrets.token_urlsafe(32)
    short = secrets.token_hex(4)
    prefix = f"{PREFIX}_{short}"
    full_key = f"{prefix}_{body}"
    return full_key, prefix, hash_api_key(full_key)


def hash_api_key(full_key: str) -> str:
    pepper = get_settings().api_key_pepper.encode()
    return hmac.new(pepper, full_key.encode(), hashlib.sha256).hexdigest()


def verify_api_key(full_key: str, stored_hash: str) -> bool:
    return hmac.compare_digest(hash_api_key(full_key), stored_hash)
