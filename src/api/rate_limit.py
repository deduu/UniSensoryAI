"""Rate limiting middleware for FastAPI.

Provides a simple in-process rate limiter using a token bucket algorithm.
Applied as a FastAPI dependency on high-traffic endpoints.

Usage::

    from src.api.rate_limit import RateLimitDep

    @app.post("/v1/process_document")
    async def process_document(
        _rate_limit: None = Depends(RateLimitDep(requests_per_minute=100)),
    ):
        ...
"""

import asyncio
import logging
import time
from typing import Optional

from fastapi import HTTPException, Request

logger = logging.getLogger(__name__)


class InProcessRateLimiter:
    """Token bucket rate limiter keyed by client IP.

    Each client IP gets its own bucket. Buckets are cleaned up
    lazily when they haven't been accessed for ``cleanup_after_s``.

    Attributes:
        requests_per_minute: Maximum requests per minute per IP.
        burst: Maximum burst size (bucket capacity).
    """

    def __init__(
        self,
        requests_per_minute: int = 100,
        burst: Optional[int] = None,
    ) -> None:
        self.rate = requests_per_minute / 60.0  # tokens per second
        self.burst = burst or requests_per_minute
        self._buckets: dict[str, dict] = {}
        self._lock = asyncio.Lock()
        self._cleanup_after_s = 300.0  # 5 minutes

    async def check(self, client_ip: str) -> None:
        """Check rate limit for a client IP.

        Args:
            client_ip: The client's IP address.

        Raises:
            HTTPException: 429 if the rate limit is exceeded.
        """
        async with self._lock:
            now = time.monotonic()

            if client_ip not in self._buckets:
                self._buckets[client_ip] = {
                    "tokens": self.burst,
                    "last_update": now,
                }

            bucket = self._buckets[client_ip]
            elapsed = now - bucket["last_update"]
            bucket["last_update"] = now

            # Refill tokens
            bucket["tokens"] = min(
                self.burst, bucket["tokens"] + elapsed * self.rate
            )

            if bucket["tokens"] < 1.0:
                retry_after = int((1.0 - bucket["tokens"]) / self.rate) + 1
                logger.warning(
                    "Rate limit exceeded for %s (retry_after=%ds)",
                    client_ip,
                    retry_after,
                )
                raise HTTPException(
                    status_code=429,
                    detail="Too many requests. Please slow down.",
                    headers={"Retry-After": str(retry_after)},
                )

            bucket["tokens"] -= 1.0

            # Lazy cleanup of stale buckets
            stale_keys = [
                k
                for k, v in self._buckets.items()
                if now - v["last_update"] > self._cleanup_after_s
                and k != client_ip
            ]
            for k in stale_keys:
                del self._buckets[k]


# Global rate limiter instance
_global_limiter = InProcessRateLimiter(requests_per_minute=100)


class RateLimitDep:
    """FastAPI dependency for rate limiting.

    Example::

        @app.post("/v1/process_document")
        async def process_document(
            request: Request,
            _: None = Depends(RateLimitDep(requests_per_minute=100)),
        ):
            ...
    """

    def __init__(
        self, requests_per_minute: int = 100, limiter: Optional[InProcessRateLimiter] = None
    ) -> None:
        self._limiter = limiter or InProcessRateLimiter(
            requests_per_minute=requests_per_minute
        )

    async def __call__(self, request: Request) -> None:
        """Check rate limit for the current request."""
        client_ip = request.client.host if request.client else "unknown"
        await self._limiter.check(client_ip)
