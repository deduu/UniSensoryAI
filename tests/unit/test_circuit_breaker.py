"""Tests for the ``CircuitBreaker`` middleware.

The breaker wraps any awaitable. After ``failure_threshold`` consecutive
failures it OPENs and fast-fails subsequent calls with
``CircuitBreakerOpen``. After ``recovery_seconds`` it allows one HALF-OPEN
probe; a success closes the breaker, a failure re-opens it.
"""

from __future__ import annotations

import asyncio

import pytest

from src.orchestration.middleware.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerOpen,
    CircuitState,
)


@pytest.mark.asyncio
async def test_breaker_starts_closed_and_passes_calls_through() -> None:
    breaker = CircuitBreaker(failure_threshold=3, recovery_seconds=60.0)

    async def succeed() -> str:
        return "ok"

    assert await breaker.call(succeed) == "ok"
    assert breaker.state == CircuitState.CLOSED


@pytest.mark.asyncio
async def test_breaker_opens_after_consecutive_failures() -> None:
    breaker = CircuitBreaker(failure_threshold=3, recovery_seconds=60.0)

    async def boom() -> None:
        raise RuntimeError("nope")

    for _ in range(3):
        with pytest.raises(RuntimeError):
            await breaker.call(boom)

    assert breaker.state == CircuitState.OPEN

    # Subsequent calls fast-fail without invoking the wrapped function.
    async def should_not_run() -> str:
        raise AssertionError("breaker should have fast-failed")

    with pytest.raises(CircuitBreakerOpen):
        await breaker.call(should_not_run)


@pytest.mark.asyncio
async def test_breaker_recovers_via_half_open_probe() -> None:
    breaker = CircuitBreaker(failure_threshold=2, recovery_seconds=0.01)

    async def boom() -> None:
        raise RuntimeError("x")

    for _ in range(2):
        with pytest.raises(RuntimeError):
            await breaker.call(boom)

    assert breaker.state == CircuitState.OPEN

    await asyncio.sleep(0.02)  # past the recovery window

    async def succeed() -> str:
        return "back"

    # First call after recovery transitions to HALF_OPEN, succeeds, and closes.
    assert await breaker.call(succeed) == "back"
    assert breaker.state == CircuitState.CLOSED


@pytest.mark.asyncio
async def test_breaker_half_open_failure_reopens() -> None:
    breaker = CircuitBreaker(failure_threshold=1, recovery_seconds=0.01)

    async def boom() -> None:
        raise RuntimeError("x")

    with pytest.raises(RuntimeError):
        await breaker.call(boom)
    assert breaker.state == CircuitState.OPEN

    await asyncio.sleep(0.02)

    # Probe call fails → breaker re-opens immediately.
    with pytest.raises(RuntimeError):
        await breaker.call(boom)
    assert breaker.state == CircuitState.OPEN


@pytest.mark.asyncio
async def test_breaker_resets_failure_count_on_success() -> None:
    breaker = CircuitBreaker(failure_threshold=3, recovery_seconds=60.0)

    async def boom() -> None:
        raise RuntimeError("x")

    async def succeed() -> str:
        return "ok"

    # 2 failures, then a success — should reset the counter.
    for _ in range(2):
        with pytest.raises(RuntimeError):
            await breaker.call(boom)
    await breaker.call(succeed)
    # Now 2 more failures must NOT open the breaker (counter was reset).
    for _ in range(2):
        with pytest.raises(RuntimeError):
            await breaker.call(boom)
    assert breaker.state == CircuitState.CLOSED
