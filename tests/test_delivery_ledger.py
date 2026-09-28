"""Notification delivery idempotency and tenant history tests."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from database.models import DatabaseManager, NotificationDelivery
from modules.alerts.delivery_ledger import DeliveryLedger


@pytest.fixture
def ledger(tmp_path: Path, seed_users):
    manager = DatabaseManager(
        f"sqlite:///{(tmp_path / 'delivery.db').as_posix()}", create_schema=True
    )
    seed_users(manager, "user_one", "user_two")
    yield DeliveryLedger(manager), manager
    manager.close()


def test_delivery_claim_is_idempotent_and_records_no_message(ledger):
    delivery_ledger, _ = ledger
    assert delivery_ledger.claim("alert_1:1", "alert_1", "user_one") is True
    assert delivery_ledger.claim("alert_1:1", "alert_1", "user_one") is False

    delivery_ledger.mark_sent("alert_1:1", "webhook")
    assert delivery_ledger.claim("alert_1:1", "alert_1", "user_one") is False
    assert delivery_ledger.list_for_user("user_one")[0]["status"] == "sent"
    assert delivery_ledger.list_for_user("user_two") == []


def test_failed_or_stale_delivery_can_be_retried(ledger):
    delivery_ledger, manager = ledger
    assert delivery_ledger.claim("alert_2:1", "alert_2", "user_one") is True
    delivery_ledger.mark_failed("alert_2:1")
    assert delivery_ledger.claim("alert_2:1", "alert_2", "user_one") is True

    session = manager.get_session()
    try:
        row = session.get(NotificationDelivery, "alert_2:1")
        row.updated_at = datetime.now() - timedelta(minutes=6)
        session.commit()
    finally:
        session.close()
    assert delivery_ledger.claim("alert_2:1", "alert_2", "user_one") is True


def test_delivery_event_cannot_be_rebound_to_another_owner(ledger):
    delivery_ledger, _ = ledger
    assert delivery_ledger.claim("alert_3:1", "alert_3", "user_one") is True
    with pytest.raises(PermissionError):
        delivery_ledger.claim("alert_3:1", "alert_3", "user_two")


def test_concurrent_delivery_claim_has_one_winner(ledger):
    delivery_ledger, manager = ledger

    with ThreadPoolExecutor(max_workers=12) as pool:
        claims = list(
            pool.map(
                lambda _: delivery_ledger.claim(
                    "alert_parallel:1",
                    "alert_parallel",
                    "user_one",
                ),
                range(20),
            )
        )

    assert claims.count(True) == 1
    assert claims.count(False) == len(claims) - 1
    session = manager.get_session()
    try:
        row = session.get(NotificationDelivery, "alert_parallel:1")
        assert row is not None
        assert row.attempts == 1
        assert row.status == "pending"
    finally:
        session.close()
