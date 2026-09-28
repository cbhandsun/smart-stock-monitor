"""
Circuit breaker pattern implementation for third-party market data sources (e.g., AkShare).
Prevents cascade timeouts and hanging worker/UI threads when external APIs are degraded.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Callable, Optional, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CircuitBreaker:
    """
    Thread-safe circuit breaker with failure threshold and cooldown period.
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 3,
        cooldown_seconds: float = 60.0,
    ) -> None:
        if failure_threshold <= 0:
            raise ValueError("failure_threshold must be positive")
        if cooldown_seconds <= 0:
            raise ValueError("cooldown_seconds must be positive")

        self.name = name
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds

        self._lock = threading.Lock()
        self._consecutive_failures: int = 0
        self._last_failure_time: float = 0.0
        self._state: str = "CLOSED"  # CLOSED, OPEN, HALF_OPEN

    @property
    def state(self) -> str:
        """Current state of the circuit breaker."""
        with self._lock:
            if self._state == "OPEN":
                now = time.monotonic()
                if now - self._last_failure_time >= self.cooldown_seconds:
                    return "HALF_OPEN"
            return self._state

    @property
    def is_open(self) -> bool:
        """Check if circuit is currently open (blocking calls)."""
        with self._lock:
            if self._state == "OPEN":
                now = time.monotonic()
                if now - self._last_failure_time >= self.cooldown_seconds:
                    self._state = "HALF_OPEN"
                    return False
                return True
            return False

    def record_success(self) -> None:
        """Record a successful execution, closing the circuit."""
        with self._lock:
            self._consecutive_failures = 0
            self._state = "CLOSED"

    def record_failure(self) -> None:
        """Record a failure, potentially opening the circuit."""
        with self._lock:
            self._consecutive_failures += 1
            self._last_failure_time = time.monotonic()
            if self._consecutive_failures >= self.failure_threshold:
                if self._state != "OPEN":
                    logger.warning(
                        "Circuit breaker '%s' opened after %d consecutive failures (cooldown: %.0fs)",
                        self.name,
                        self._consecutive_failures,
                        self.cooldown_seconds,
                    )
                self._state = "OPEN"

    def call(self, func: Callable[[], T], fallback: Optional[T] = None) -> Optional[T]:
        """
        Execute func protected by the circuit breaker.
        Returns fallback if circuit is open or func raises an Exception.
        """
        if self.is_open:
            logger.debug(
                "Circuit breaker '%s' is OPEN; skipping call",
                self.name,
            )
            return fallback

        try:
            result = func()
            self.record_success()
            return result
        except Exception:
            self.record_failure()
            logger.warning(
                "Call protected by circuit breaker '%s' failed",
                self.name,
            )
            return fallback

    def reset(self) -> None:
        """Manually reset the circuit breaker to CLOSED state."""
        with self._lock:
            self._consecutive_failures = 0
            self._last_failure_time = 0.0
            self._state = "CLOSED"


akshare_circuit_breaker = CircuitBreaker("akshare", failure_threshold=3, cooldown_seconds=60.0)
