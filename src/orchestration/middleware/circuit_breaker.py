"""Async circuit-breaker for wrapping flaky external calls.

States:

- CLOSED:    calls flow through; failures increment a counter.
- OPEN:      ``failure_threshold`` consecutive failures hit → calls fast-fail
             with ``CircuitBreakerOpen`` for ``recovery_seconds``.
- HALF_OPEN: one probe call is allowed; success → CLOSED, failure → OPEN.

A successful call from CLOSED resets the failure counter, so transient
blips don't accumulate over long runtimes.
"""

from __future__ import annotations

import asyncio
import enum
import time
from typing import Awaitable, Callable, TypeVar

T = TypeVar("T")


class CircuitState(str, enum.Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreakerOpen(RuntimeError):
    """Raised when a call is fast-failed because the breaker is OPEN."""


class CircuitBreaker:
    """Threshold + cooldown breaker for async callables.

    Args:
        failure_threshold: Consecutive failures that trip the breaker.
        recovery_seconds: How long OPEN stays in effect before a HALF_OPEN
            probe is allowed.
        name: Identifier used in error messages.
    """

    def __init__(
        self,
        *,
        failure_threshold: int = 3,
        recovery_seconds: float = 60.0,
        name: str = "circuit",
    ) -> None:
        if failure_threshold < 1:
            raise ValueError("failure_threshold must be >= 1")
        if recovery_seconds <= 0:
            raise ValueError("recovery_seconds must be > 0")
        self._failure_threshold = failure_threshold
        self._recovery_seconds = recovery_seconds
        self._name = name

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._opened_at: float | None = None
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        return self._state

    @property
    def name(self) -> str:
        return self._name

    async def call(self, fn: Callable[[], Awaitable[T]]) -> T:
        """Run ``fn`` through the breaker.

        ``fn`` is a zero-arg coroutine factory — bind arguments at the
        call site (e.g. ``breaker.call(lambda: client.get(url))``) so the
        breaker stays callable-shape-agnostic.

        Raises:
            CircuitBreakerOpen: When the breaker is OPEN.
            Any exception ``fn`` raises (after recording the failure).
        """
        async with self._lock:
            if self._state == CircuitState.OPEN:
                if self._cooldown_expired():
                    self._state = CircuitState.HALF_OPEN
                else:
                    raise CircuitBreakerOpen(
                        f"{self._name}: circuit is open; retry after cooldown"
                    )

        try:
            result = await fn()
        except Exception:
            await self._record_failure()
            raise
        else:
            await self._record_success()
            return result

    def _cooldown_expired(self) -> bool:
        return (
            self._opened_at is not None
            and (time.monotonic() - self._opened_at) >= self._recovery_seconds
        )

    async def _record_success(self) -> None:
        async with self._lock:
            self._failure_count = 0
            self._state = CircuitState.CLOSED
            self._opened_at = None

    async def _record_failure(self) -> None:
        async with self._lock:
            self._failure_count += 1
            if self._state == CircuitState.HALF_OPEN:
                # Probe failed — reopen immediately.
                self._state = CircuitState.OPEN
                self._opened_at = time.monotonic()
                return
            if self._failure_count >= self._failure_threshold:
                self._state = CircuitState.OPEN
                self._opened_at = time.monotonic()
