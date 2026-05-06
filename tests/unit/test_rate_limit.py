"""Tests for src/api/rate_limit.py — token bucket rate limiter."""

import asyncio

import pytest
from fastapi import HTTPException

from src.api.rate_limit import InProcessRateLimiter, RateLimitDep


class TestInProcessRateLimiter:
    @pytest.mark.asyncio
    async def test_allows_requests_under_limit(self):
        """Requests under the limit should pass."""
        limiter = InProcessRateLimiter(requests_per_minute=60, burst=10)
        # 5 requests should all pass (burst=10)
        for _ in range(5):
            await limiter.check("10.0.0.1")

    @pytest.mark.asyncio
    async def test_rejects_requests_over_burst(self):
        """Exceeding burst should raise 429."""
        limiter = InProcessRateLimiter(requests_per_minute=60, burst=3)
        # Use up all burst tokens
        for _ in range(3):
            await limiter.check("10.0.0.1")

        # 4th request should be rejected
        with pytest.raises(HTTPException) as exc_info:
            await limiter.check("10.0.0.1")
        assert exc_info.value.status_code == 429
        assert "Retry-After" in exc_info.value.headers

    @pytest.mark.asyncio
    async def test_separate_limits_per_ip(self):
        """Different IPs should have independent limits."""
        limiter = InProcessRateLimiter(requests_per_minute=60, burst=2)

        # Use up IP-1's quota
        await limiter.check("10.0.0.1")
        await limiter.check("10.0.0.1")

        # IP-2 should still have tokens
        await limiter.check("10.0.0.2")  # Should not raise

    @pytest.mark.asyncio
    async def test_tokens_refill_over_time(self):
        """Tokens should refill after enough time passes."""
        limiter = InProcessRateLimiter(requests_per_minute=600, burst=1)
        # Use the one burst token
        await limiter.check("10.0.0.1")

        # Wait for refill (600/min = 10/s, so 0.15s should give us ~1.5 tokens)
        await asyncio.sleep(0.15)

        # Should pass now
        await limiter.check("10.0.0.1")


class TestRateLimitDep:
    @pytest.mark.asyncio
    async def test_dep_passes_request(self):
        """Dependency should extract client IP and check rate limit."""
        from unittest.mock import MagicMock

        dep = RateLimitDep(requests_per_minute=100)
        mock_request = MagicMock()
        mock_request.client.host = "10.0.0.1"

        # Should not raise
        await dep(mock_request)

    @pytest.mark.asyncio
    async def test_dep_rejects_over_limit(self):
        """Dependency should raise 429 when limit exceeded."""
        from unittest.mock import MagicMock

        limiter = InProcessRateLimiter(requests_per_minute=60, burst=1)
        dep = RateLimitDep(requests_per_minute=60, limiter=limiter)
        mock_request = MagicMock()
        mock_request.client.host = "10.0.0.1"

        await dep(mock_request)  # Use the 1 burst token

        with pytest.raises(HTTPException) as exc_info:
            await dep(mock_request)
        assert exc_info.value.status_code == 429
