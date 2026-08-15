"""Reversible encryption for webhook signing secrets at rest."""
from __future__ import annotations

import base64
import hashlib

from app.core.config import get_settings


def _fernet():
    from cryptography.fernet import Fernet

    settings = get_settings()
    key = base64.urlsafe_b64encode(
        hashlib.sha256(settings.api_key_pepper.encode()).digest()
    )
    return Fernet(key)


def encrypt_secret(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt_secret(ciphertext: str) -> str:
    return _fernet().decrypt(ciphertext.encode()).decode()
