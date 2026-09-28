"""Outbound URL validation for administrator-configured webhooks."""

from __future__ import annotations

from urllib.parse import urlsplit


def validate_https_webhook(value: object, allowed_hosts: set[str]) -> str | None:
    """Return a safe HTTPS webhook URL restricted to an explicit host allowlist."""
    if not isinstance(value, str) or not value or len(value) > 2048:
        return None
    try:
        parsed = urlsplit(value)
    except ValueError:
        return None
    hostname = (parsed.hostname or "").lower().rstrip(".")
    normalized_hosts = {host.lower().rstrip(".") for host in allowed_hosts if host}
    if (
        parsed.scheme != "https"
        or not hostname
        or hostname not in normalized_hosts
        or parsed.username is not None
        or parsed.password is not None
        or parsed.fragment
    ):
        return None
    return value
