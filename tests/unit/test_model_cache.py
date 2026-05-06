"""Tests for src/models/cache.py — ModelCacheManager with LRU + OOM."""

import sys
from unittest.mock import MagicMock, patch

import pytest

# Mock heavy ML modules
_MOCK_MODULES = [
    "torch", "torch.cuda", "torch.nn", "torch.nn.functional",
    "torchvision", "torchvision.transforms",
    "transformers", "accelerate", "bitsandbytes",
]
for mod in _MOCK_MODULES:
    if mod not in sys.modules:
        sys.modules[mod] = MagicMock()

from src.models.cache import ModelCacheManager


def _mock_model(name: str = "test") -> MagicMock:
    """Create a mock model with unload()."""
    mock = MagicMock()
    mock.name = name
    mock.unload = MagicMock()
    return mock


@pytest.fixture
def cache():
    """Small cache for testing (max 2 models)."""
    return ModelCacheManager(max_models=2)


class TestModelCacheManager:
    @pytest.mark.asyncio
    async def test_cache_returns_existing_model(self, cache):
        """Repeated get_or_load should return the same instance."""
        model_a = _mock_model("model_a")
        with patch.object(cache, "_load_model", return_value=model_a) as mock_load:
            result1 = await cache.get_or_load("model-a")
            result2 = await cache.get_or_load("model-a")
            mock_load.assert_called_once()

        assert result1 is result2
        assert cache.size == 1

    @pytest.mark.asyncio
    async def test_cache_evicts_lru_on_capacity(self, cache):
        """When cache is full, loading a new model should evict the LRU."""
        model_a = _mock_model("a")
        model_b = _mock_model("b")
        model_c = _mock_model("c")

        with patch.object(
            cache, "_load_model", side_effect=[model_a, model_b, model_c]
        ):
            await cache.get_or_load("model-a")
            await cache.get_or_load("model-b")
            # Cache is full (max_models=2). Loading model-c evicts model-a.
            await cache.get_or_load("model-c")

        assert cache.size == 2
        assert "model-a" not in cache.cached_keys
        assert "model-b" in cache.cached_keys
        assert "model-c" in cache.cached_keys

    @pytest.mark.asyncio
    async def test_cache_calls_unload_on_eviction(self, cache):
        """Evicted models should have unload() called."""
        model_a = _mock_model("a")
        model_b = _mock_model("b")
        model_c = _mock_model("c")

        with patch.object(
            cache, "_load_model", side_effect=[model_a, model_b, model_c]
        ):
            await cache.get_or_load("model-a")
            await cache.get_or_load("model-b")
            await cache.get_or_load("model-c")

        model_a.unload.assert_called_once()

    @pytest.mark.asyncio
    async def test_cache_lru_updates_on_access(self, cache):
        """Accessing a cached model should move it to MRU position."""
        model_a = _mock_model("a")
        model_b = _mock_model("b")
        model_c = _mock_model("c")

        with patch.object(
            cache, "_load_model", side_effect=[model_a, model_b, model_c]
        ):
            await cache.get_or_load("model-a")
            await cache.get_or_load("model-b")
            # Access model-a again (moves it to MRU)
            await cache.get_or_load("model-a")
            # Now load model-c — should evict model-b (LRU)
            await cache.get_or_load("model-c")

        assert cache.size == 2
        assert "model-a" in cache.cached_keys
        assert "model-c" in cache.cached_keys
        model_b.unload.assert_called_once()

    @pytest.mark.asyncio
    async def test_cache_retries_on_oom(self, cache):
        """OOM on first load should evict all and retry."""
        model_a = _mock_model("a")
        model_b = _mock_model("b")

        with patch.object(cache, "_load_model", side_effect=[model_a]):
            await cache.get_or_load("model-a")

        # Now trying to load model-b triggers OOM first, then succeeds
        call_count = 0

        def oom_then_success(model_id, api_keys=None):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("CUDA out of memory")
            return model_b

        with patch.object(cache, "_load_model", side_effect=oom_then_success):
            result = await cache.get_or_load("model-b")

        assert result is model_b
        model_a.unload.assert_called_once()  # Evicted during OOM recovery

    @pytest.mark.asyncio
    async def test_cache_fails_after_retry_exhausted(self, cache):
        """If OOM persists after retry, should raise RuntimeError."""
        with patch.object(
            cache,
            "_load_model",
            side_effect=RuntimeError("CUDA out of memory"),
        ):
            with pytest.raises(RuntimeError, match="Failed to load model"):
                await cache.get_or_load("model-x")

    @pytest.mark.asyncio
    async def test_cache_different_api_keys_separate_entries(self, cache):
        """Same model_id with different api_keys should be cached separately."""
        model_a = _mock_model("a")
        model_b = _mock_model("b")

        with patch.object(
            cache, "_load_model", side_effect=[model_a, model_b]
        ):
            r1 = await cache.get_or_load("model-x", api_keys={"key": "val1"})
            r2 = await cache.get_or_load("model-x", api_keys={"key": "val2"})

        assert r1 is not r2
        assert cache.size == 2
