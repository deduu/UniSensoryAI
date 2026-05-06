"""Model cache manager — LRU eviction with OOM protection.

Replaces the bare MODEL_CACHE dict with a proper async-safe cache
that evicts least-recently-used models and handles CUDA OOM gracefully.
"""

import asyncio
import hashlib
import json
import logging
from collections import OrderedDict
from typing import Any, Dict, Optional

from src.core.base import BaseVisionLanguageModel
from src.models import ModelLoader
from src.utils.config import ConfigLoader

logger = logging.getLogger(__name__)


class ModelCacheManager:
    """Thread-safe LRU model cache with OOM protection.

    Models are cached by a key derived from (model_id, api_keys).
    When the cache exceeds ``max_models``, the least-recently-used
    model is evicted (its ``unload()`` method is called).

    On CUDA OutOfMemoryError during loading, the cache evicts all
    models and retries once before failing.

    Attributes:
        max_models: Maximum number of models to keep in cache.
    """

    def __init__(self, max_models: int = 3) -> None:
        self._cache: OrderedDict[str, BaseVisionLanguageModel] = OrderedDict()
        self._lock = asyncio.Lock()
        self._max_models = max_models

    @property
    def max_models(self) -> int:
        """Maximum cache capacity."""
        return self._max_models

    @property
    def size(self) -> int:
        """Current number of cached models."""
        return len(self._cache)

    @property
    def cached_keys(self) -> list[str]:
        """List of currently cached model keys (oldest first)."""
        return list(self._cache.keys())

    @staticmethod
    def _make_key(model_id: str, api_keys: Optional[Dict[str, str]] = None) -> str:
        """Build a stable cache key from model_id and optional api_keys."""
        if not api_keys:
            return model_id
        keys_str = json.dumps(api_keys, sort_keys=True)
        keys_hash = hashlib.md5(keys_str.encode()).hexdigest()
        return f"{model_id}_{keys_hash}"

    async def get_or_load(
        self,
        model_id: str,
        api_keys: Optional[Dict[str, str]] = None,
    ) -> BaseVisionLanguageModel:
        """Retrieve a model from cache, or load and cache it.

        Args:
            model_id: Model identifier from models.yaml.
            api_keys: Optional API key overrides.

        Returns:
            Loaded model instance.

        Raises:
            RuntimeError: If model loading fails even after OOM recovery.
        """
        key = self._make_key(model_id, api_keys)

        async with self._lock:
            # Cache hit — move to end (most recently used)
            if key in self._cache:
                self._cache.move_to_end(key)
                logger.info("Model cache hit: %s", key)
                return self._cache[key]

            # Cache miss — load
            logger.info("Model cache miss: %s. Loading...", key)

            # Evict LRU if at capacity
            if len(self._cache) >= self._max_models:
                self._evict_lru()

            # Load with OOM protection
            try:
                model = self._load_model(model_id, api_keys)
            except (RuntimeError, Exception) as e:
                if self._is_oom_error(e):
                    logger.warning(
                        "OOM during model load. Evicting all and retrying..."
                    )
                    self._evict_all()
                    try:
                        model = self._load_model(model_id, api_keys)
                    except Exception as retry_err:
                        logger.error(
                            "Model load failed after OOM recovery: %s", retry_err
                        )
                        raise RuntimeError(
                            f"Failed to load model '{model_id}' even after "
                            f"evicting all cached models: {retry_err}"
                        ) from retry_err
                else:
                    raise

            self._cache[key] = model
            return model

    def _load_model(
        self, model_id: str, api_keys: Optional[Dict[str, str]] = None
    ) -> BaseVisionLanguageModel:
        """Load a model via ConfigLoader + ModelLoader.

        Args:
            model_id: Model identifier.
            api_keys: Optional API key overrides.

        Returns:
            Loaded model instance.
        """
        model_config = ConfigLoader.get_model_config(model_id, api_keys=api_keys)
        return ModelLoader.load_model(model_config)

    def _evict_lru(self) -> None:
        """Evict the least recently used model."""
        if not self._cache:
            return
        evicted_key, evicted_model = self._cache.popitem(last=False)
        logger.info("Evicting LRU model: %s", evicted_key)
        try:
            evicted_model.unload()
        except Exception as e:
            logger.warning("Error unloading model %s: %s", evicted_key, e)

    def _evict_all(self) -> None:
        """Evict all cached models."""
        logger.info("Evicting all %d cached models", len(self._cache))
        for key in list(self._cache.keys()):
            model = self._cache.pop(key)
            try:
                model.unload()
            except Exception as e:
                logger.warning("Error unloading model %s: %s", key, e)

    @staticmethod
    def _is_oom_error(exc: Exception) -> bool:
        """Check if an exception is a CUDA OOM error."""
        error_str = str(exc).lower()
        return (
            "out of memory" in error_str
            or "cuda" in error_str
            or "oom" in error_str
        )
