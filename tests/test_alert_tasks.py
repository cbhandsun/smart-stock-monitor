"""Regression tests for tenant-aware Celery alert processing."""

from types import SimpleNamespace

from tasks import alerts as alert_tasks


class _FakeDb:
    def get_active_alert_user_ids(self):
        return ["user_one", "user_two"]

    def get_triggered_alert_user_ids(self):
        return ["user_one", "user_two"]


class _FakeCache:
    def get_stock_data(self, symbol, data_type):
        assert data_type == "quote"
        return {"price": 101.0, "symbol": symbol}


class _FakeAlertManager:
    checked_users = []
    removed = []

    def __init__(self, user_id):
        self.user_id = user_id

    def get_active_alerts(self):
        symbol = "600519" if self.user_id == "user_one" else "000001"
        return [
            SimpleNamespace(
                id=f"alert_{self.user_id}", symbol=symbol, message=self.user_id
            )
        ]

    def check_all_alerts(self, market_data):
        self.checked_users.append((self.user_id, frozenset(market_data)))
        symbol = next(iter(market_data))
        return [
            SimpleNamespace(
                id=f"triggered_{self.user_id}",
                user_id=self.user_id,
                symbol=symbol,
                message=self.user_id,
                trigger_count=1,
            )
        ]

    def get_triggered_alerts(self):
        return [
            SimpleNamespace(
                id=f"old_{self.user_id}",
                triggered_at="2000-01-01T00:00:00",
            )
        ]

    def remove_alert(self, alert_id):
        self.removed.append((self.user_id, alert_id))
        return True


def test_check_all_alerts_processes_every_owner(monkeypatch):
    _FakeAlertManager.checked_users = []
    delayed = []
    monkeypatch.setattr(alert_tasks, "is_trading_hours", lambda: True)
    monkeypatch.setattr(alert_tasks, "get_db", lambda: _FakeDb())
    monkeypatch.setattr(alert_tasks, "RedisCache", _FakeCache)
    monkeypatch.setattr(alert_tasks, "AlertManager", _FakeAlertManager)
    monkeypatch.setattr(
        alert_tasks.send_alert_notification,
        "delay",
        lambda event_key, user_id, alert_id, message: delayed.append(
            (event_key, user_id, alert_id, message)
        ),
    )

    result = alert_tasks.check_all_alerts.run()

    assert result == "Checked 2 alerts, 2 triggered"
    assert set(_FakeAlertManager.checked_users) == {
        ("user_one", frozenset({"600519"})),
        ("user_two", frozenset({"000001"})),
    }
    assert {alert_id for _, _, alert_id, _ in delayed} == {
        "triggered_user_one",
        "triggered_user_two",
    }
    assert {event_key for event_key, _, _, _ in delayed} == {
        "triggered_user_one:1",
        "triggered_user_two:1",
    }


def test_cleanup_triggered_alerts_preserves_owner_context(monkeypatch):
    _FakeAlertManager.removed = []
    monkeypatch.setattr(alert_tasks, "get_db", lambda: _FakeDb())
    monkeypatch.setattr(alert_tasks, "AlertManager", _FakeAlertManager)

    result = alert_tasks.cleanup_triggered_alerts.run(days=7)

    assert result == "Removed 2 old alerts"
    assert set(_FakeAlertManager.removed) == {
        ("user_one", "old_user_one"),
        ("user_two", "old_user_two"),
    }
