"""LRU cache for per-page VLM inference results.

Repeated processing of the same page (image_bytes + prompt + model + schema)
is wasted work — common across retries, re-uploads, and test reruns. This
cache is keyed by a sha256 over those inputs and is bounded by an LRU policy
with a TTL.

Concurrency: a single ``asyncio.Lock`` guards inserts and eviction. Reads do
not take the lock; Python dict access is atomic and the worst case is a
near-eviction race that returns a still-correct value just before its
eviction completes.
"""

import asyncio
import hashlib
import logging
import time
from collections import OrderedDict
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


class InferenceResultCache:
    """Bounded LRU cache for VLM extraction results.

    Args:
        max_entries: LRU eviction threshold.
        ttl_seconds: Entries older than this are treated as misses.
    """

    def __init__(
        self, max_entries: int = 2000, ttl_seconds: float = 3600.0
    ) -> None:
        self._store: "OrderedDict[str, Tuple[float, str]]" = OrderedDict()
        self._lock = asyncio.Lock()
        self._max_entries = max_entries
        self._ttl_seconds = ttl_seconds
        self.hits = 0
        self.misses = 0

    @staticmethod
    def make_key(
        image_bytes: bytes,
        prompt: str,
        model_id: str,
        schema_id: Optional[str] = None,
    ) -> str:
        """Build a stable cache key over the inputs to a single inference call."""
        h = hashlib.sha256()
        h.update(image_bytes)
        h.update(b"\x1f")
        h.update(prompt.encode("utf-8"))
        h.update(b"\x1f")
        h.update(model_id.encode("utf-8"))
        h.update(b"\x1f")
        if schema_id:
            h.update(schema_id.encode("utf-8"))
        return h.hexdigest()

    async def get(self, key: str) -> Optional[str]:
        """Return the cached value for ``key`` or ``None`` if absent/expired."""
        entry = self._store.get(key)
        if entry is None:
            self.misses += 1
            return None
        timestamp, value = entry
        if time.monotonic() - timestamp > self._ttl_seconds:
            async with self._lock:
                self._store.pop(key, None)
            self.misses += 1
            return None
        async with self._lock:
            if key in self._store:
                self._store.move_to_end(key)
        self.hits += 1
        return value

    async def set(self, key: str, value: str) -> None:
        """Insert ``value`` under ``key``, evicting LRU if over capacity."""
        async with self._lock:
            self._store[key] = (time.monotonic(), value)
            self._store.move_to_end(key)
            while len(self._store) > self._max_entries:
                evicted_key, _ = self._store.popitem(last=False)
                logger.debug("InferenceResultCache: evicted %s", evicted_key)

    @property
    def size(self) -> int:
        return len(self._store)

    def clear(self) -> None:
        """Drop all entries — test-only seam."""
        self._store.clear()
        self.hits = 0
        self.misses = 0


_cache: Optional[InferenceResultCache] = None


def get_cache() -> InferenceResultCache:
    """Return the module-level singleton cache."""
    global _cache
    if _cache is None:
        _cache = InferenceResultCache()
    return _cache


def reset_cache() -> None:
    """Reset the singleton — test-only seam."""
    global _cache
    _cache = None
