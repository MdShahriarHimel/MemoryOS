"""Webhook URL validation — blocks SSRF to private/internal targets."""
from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

from app.core.errors import ValidationError

_BLOCKED_HOSTS = frozenset({"localhost", "metadata.google.internal"})


def validate_webhook_url(url: str) -> str:
    parsed = urlparse(url.strip())
    if parsed.scheme not in ("http", "https"):
        raise ValidationError("Webhook URL must use http or https.", details={"url": url})
    if not parsed.hostname:
        raise ValidationError("Webhook URL must include a hostname.", details={"url": url})
    host = parsed.hostname.lower()
    if host in _BLOCKED_HOSTS:
        raise ValidationError("Webhook URL host is not allowed.", details={"host": host})
    if host.endswith(".local") or host.endswith(".internal"):
        raise ValidationError("Webhook URL host is not allowed.", details={"host": host})

    # Resolve and reject private/link-local/loopback IPs
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        raise ValidationError("Webhook URL hostname could not be resolved.", details={"host": host})

    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
        ):
            raise ValidationError(
                "Webhook URL must not target a private or internal address.",
                details={"host": host, "ip": str(ip)},
            )
    return url
