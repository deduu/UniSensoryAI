"""Tests for src/inference/result_cache.py — InferenceResultCache."""

import asyncio
import time

import pytest

from src.inference.result_cache import (
    InferenceResultCache,
    get_cache,
    reset_cache,
)


@pytest.fixture(autouse=True)
def _reset_singleton():
    reset_cache()
    yield
    reset_cache()


class TestMakeKey:
    def test_same_inputs_same_key(self):
        a = InferenceResultCache.make_key(b"abc", "prompt", "m1")
        b = InferenceResultCache.make_key(b"abc", "prompt", "m1")
        assert a == b

    def test_different_bytes_differ(self):
        a = InferenceResultCache.make_key(b"abc", "prompt", "m1")
        b = InferenceResultCache.make_key(b"abd", "prompt", "m1")
        assert a != b

    def test_different_prompt_differ(self):
        a = InferenceResultCache.make_key(b"abc", "prompt-a", "m1")
        b = InferenceResultCache.make_key(b"abc", "prompt-b", "m1")
        assert a != b

    def test_different_model_differ(self):
        a = InferenceResultCache.make_key(b"abc", "prompt", "m1")
        b = InferenceResultCache.make_key(b"abc", "prompt", "m2")
        assert a != b

    def test_schema_id_changes_key(self):
        a = InferenceResultCache.make_key(b"abc", "prompt", "m1")
        b = InferenceResultCache.make_key(b"abc", "prompt", "m1", schema_id="s1")
        assert a != b


class TestCacheBehavior:
    @pytest.mark.asyncio
    async def test_miss_then_set_then_hit(self):
        cache = InferenceResultCache(max_entries=10)
        key = cache.make_key(b"img", "p", "m")

        assert await cache.get(key) is None
        assert cache.misses == 1
        assert cache.hits == 0

        await cache.set(key, "extracted")
        assert await cache.get(key) == "extracted"
        assert cache.hits == 1

    @pytest.mark.asyncio
    async def test_lru_eviction(self):
        cache = InferenceResultCache(max_entries=2)
        await cache.set("a", "1")
        await cache.set("b", "2")
        await cache.set("c", "3")  # evicts "a"

        assert cache.size == 2
        assert await cache.get("a") is None
        assert await cache.get("b") == "2"
        assert await cache.get("c") == "3"

    @pytest.mark.asyncio
    async def test_get_promotes_to_mru(self):
        cache = InferenceResultCache(max_entries=2)
        await cache.set("a", "1")
        await cache.set("b", "2")
        # Touch "a" — it becomes MRU; next insertion should evict "b".
        await cache.get("a")
        await cache.set("c", "3")

        assert await cache.get("a") == "1"
        assert await cache.get("b") is None
        assert await cache.get("c") == "3"

    @pytest.mark.asyncio
    async def test_ttl_expiry(self):
        cache = InferenceResultCache(max_entries=10, ttl_seconds=0.05)
        await cache.set("k", "v")
        assert await cache.get("k") == "v"
        await asyncio.sleep(0.1)
        assert await cache.get("k") is None


class TestSingleton:
    def test_get_cache_returns_singleton(self):
        a = get_cache()
        b = get_cache()
        assert a is b

    def test_reset_cache_replaces_instance(self):
        a = get_cache()
        reset_cache()
        b = get_cache()
        assert a is not b
