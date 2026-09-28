"""
Unit tests for core.circuit_breaker (CircuitBreaker).
Validates state transitions, failure threshold, cooldown recovery, and thread safety.
"""

from __future__ import annotations

import time
import pytest
from core.circuit_breaker import CircuitBreaker


def test_circuit_breaker_init_validation():
    with pytest.raises(ValueError, match="failure_threshold"):
        CircuitBreaker("test", failure_threshold=0)
    with pytest.raises(ValueError, match="cooldown_seconds"):
        CircuitBreaker("test", cooldown_seconds=0)


def test_circuit_breaker_normal_execution():
    cb = CircuitBreaker("test_ok", failure_threshold=3, cooldown_seconds=1.0)
    assert not cb.is_open
    assert cb.state == "CLOSED"

    called = False

    def succeed():
        nonlocal called
        called = True
        return 42

    res = cb.call(succeed)
    assert res == 42
    assert called
    assert not cb.is_open
    assert cb.state == "CLOSED"


def test_circuit_breaker_opens_on_consecutive_failures():
    cb = CircuitBreaker("test_fail", failure_threshold=3, cooldown_seconds=0.5)

    def failing():
        raise ConnectionResetError("Connection dropped")

    # Failure 1
    assert cb.call(failing, fallback="fallback_1") == "fallback_1"
    assert not cb.is_open
    assert cb.state == "CLOSED"

    # Failure 2
    assert cb.call(failing, fallback="fallback_2") == "fallback_2"
    assert not cb.is_open
    assert cb.state == "CLOSED"

    # Failure 3 -> opens
    assert cb.call(failing, fallback="fallback_3") == "fallback_3"
    assert cb.is_open
    assert cb.state == "OPEN"

    # Next call is skipped without executing func
    executed = False

    def never_called():
        nonlocal executed
        executed = True
        return "not_reached"

    assert cb.call(never_called, fallback="circuit_open_fallback") == "circuit_open_fallback"
    assert not executed


def test_circuit_breaker_half_open_and_recovery():
    cb = CircuitBreaker("test_recovery", failure_threshold=2, cooldown_seconds=0.1)

    def failing():
        raise TimeoutError("timeout")

    cb.call(failing)
    cb.call(failing)
    assert cb.is_open
    assert cb.state == "OPEN"

    # Wait for cooldown to expire
    time.sleep(0.12)

    # Cooldown expired -> is_open becomes False, state becomes HALF_OPEN
    assert not cb.is_open
    assert cb.state == "HALF_OPEN"

    # Successful call in HALF_OPEN resets to CLOSED
    res = cb.call(lambda: "recovered")
    assert res == "recovered"
    assert cb.state == "CLOSED"
    assert not cb.is_open


def test_circuit_breaker_half_open_failure_reopens():
    cb = CircuitBreaker("test_reopen", failure_threshold=1, cooldown_seconds=0.1)

    def failing():
        raise RuntimeError("boom")

    cb.call(failing)
    assert cb.is_open

    time.sleep(0.12)
    assert cb.state == "HALF_OPEN"

    # Failing again in HALF_OPEN reopens circuit
    cb.call(failing)
    assert cb.is_open
    assert cb.state == "OPEN"


def test_circuit_breaker_manual_reset():
    cb = CircuitBreaker("test_reset", failure_threshold=1, cooldown_seconds=10.0)
    cb.call(lambda: (_ for _ in ()).throw(ValueError("err")))
    assert cb.is_open

    cb.reset()
    assert not cb.is_open
    assert cb.state == "CLOSED"
