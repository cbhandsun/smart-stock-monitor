"""Security tests for outbound webhook URL allowlisting."""

import pytest

from core.url_security import validate_https_webhook
from tasks import alerts as alert_tasks


@pytest.mark.parametrize(
    "url",
    [
        None,
        "",
        "http://hooks.example.com/path",
        "https://localhost/path",
        "https://127.0.0.1/path",
        "https://user:pass@hooks.example.com/path",
        "https://hooks.example.com/path#fragment",
        "https://evil.example/path",
    ],
)
def test_webhook_url_rejects_unsafe_or_unlisted_targets(url):
    assert validate_https_webhook(url, {"hooks.example.com"}) is None


def test_webhook_url_accepts_exact_https_allowlisted_host():
    url = "https://hooks.example.com/services/tenant/token"
    assert validate_https_webhook(url, {"hooks.example.com"}) == url


def test_generic_webhook_is_disabled_without_host_allowlist(monkeypatch):
    monkeypatch.setenv("ALERT_WEBHOOK_URL", "https://hooks.example.com/path")
    monkeypatch.delenv("ALERT_WEBHOOK_ALLOWED_HOSTS", raising=False)

    assert alert_tasks._send_generic_webhook("alert_1", "title", "content") is False


def test_notification_rejects_oversized_user_content():
    with pytest.raises(ValueError, match="message"):
        alert_tasks._deliver_notification("alert_1", "x" * 501)
