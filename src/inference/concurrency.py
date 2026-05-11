"""Per-model asyncio semaphore registry.

Page-level parallel inference must respect per-model concurrency limits so we
do not exhaust local GPU memory or trip cloud provider rate ceilings. This
registry hands out one ``asyncio.Semaphore`` per ``model_id``, sized from the
``concurrency:`` key in ``configs/models.yaml`` (or a provider-based default).
"""

import asyncio
import logging
from typing import Dict, Optional

from src.utils.config import ConfigLoader

logger = logging.getLogger(__name__)

_LOCAL_PROVIDERS = {"huggingface", "qwen", "llava", "lightonocr", "deepseek"}
_CLOUD_PROVIDERS = {
    "openai", "google", "together", "fireworks", "openrouter", "deepinfra",
}
_DEFAULT_LOCAL_CONCURRENCY = 1
_DEFAULT_CLOUD_CONCURRENCY = 8


class ModelSemaphoreRegistry:
    """Registry of per-model asyncio semaphores.

    One semaphore per ``model_id`` gates the number of concurrent
    ``model.process`` invocations against that model. Limits are resolved
    once per model and cached for the lifetime of the registry. Creation
    is guarded by an ``asyncio.Lock`` so concurrent coroutines racing for
    the same id cannot produce two different semaphores.
    """

    def __init__(self) -> None:
        self._semaphores: Dict[str, asyncio.Semaphore] = {}
        self._limits: Dict[str, int] = {}
        self._lock = asyncio.Lock()

    async def get(self, model_id: str) -> asyncio.Semaphore:
        """Return (creating if needed) the semaphore for ``model_id``."""
        existing = self._semaphores.get(model_id)
        if existing is not None:
            return existing
        async with self._lock:
            existing = self._semaphores.get(model_id)
            if existing is not None:
                return existing
            limit = self._resolve_limit(model_id)
            sem = asyncio.Semaphore(limit)
            self._semaphores[model_id] = sem
            self._limits[model_id] = limit
            logger.info(
                "ModelSemaphoreRegistry: %s -> concurrency=%d", model_id, limit
            )
            return sem

    def get_limit(self, model_id: str) -> int:
        """Return the resolved limit, or 0 if the model has never been requested."""
        return self._limits.get(model_id, 0)

    @staticmethod
    def _resolve_limit(model_id: str) -> int:
        """Look up the limit for ``model_id``.

        1. explicit ``concurrency:`` key in models.yaml.
        2. provider-based default (cloud=8, local=1).
        3. fall back to 1 if the config cannot be read.
        """
        try:
            cfg = ConfigLoader.get_model_config(model_id, validate=False)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "ModelSemaphoreRegistry: cannot read config for %s (%s); "
                "falling back to 1",
                model_id,
                exc,
            )
            return 1

        explicit = cfg.get("concurrency")
        if isinstance(explicit, int) and explicit > 0:
            return explicit

        provider = (cfg.get("provider") or "").lower()
        if provider in _CLOUD_PROVIDERS:
            return _DEFAULT_CLOUD_CONCURRENCY
        if provider in _LOCAL_PROVIDERS:
            return _DEFAULT_LOCAL_CONCURRENCY
        return 1


_registry: Optional[ModelSemaphoreRegistry] = None


def get_registry() -> ModelSemaphoreRegistry:
    """Return the module-level singleton registry."""
    global _registry
    if _registry is None:
        _registry = ModelSemaphoreRegistry()
    return _registry


def reset_registry() -> None:
    """Reset the singleton — test-only seam."""
    global _registry
    _registry = None
