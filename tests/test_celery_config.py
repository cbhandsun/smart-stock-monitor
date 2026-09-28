"""Celery reliability configuration regression tests."""

from tasks.celery_config import celery_app


def test_broker_retries_are_explicit_for_startup_and_runtime():
    assert celery_app.conf.broker_connection_retry is True
    assert celery_app.conf.broker_connection_retry_on_startup is True
