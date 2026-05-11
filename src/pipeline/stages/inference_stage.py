"""Inference stage — runs VLM inference on content items in parallel."""

import asyncio
import io
import logging
from typing import Any, Dict, List

from src.core.base import BasePipelineStage
from src.inference.concurrency import get_registry
from src.inference.result_cache import InferenceResultCache, get_cache
from src.pipeline.prompts import get_prompts

logger = logging.getLogger(__name__)


class InferenceStage(BasePipelineStage):
    """Loads the specified model and runs inference on each content item.

    Image items fan out via ``asyncio.gather``; concurrency is bounded by a
    per-model ``asyncio.Semaphore`` from ``ModelSemaphoreRegistry``. Identical
    ``(image_bytes, prompt, model_id)`` inputs are served from
    ``InferenceResultCache`` and skip the model entirely.

    Text items (already-extracted Office content) pass through unchanged.

    Reads:
        - ``model_id``
        - ``api_keys`` (optional)
        - ``content_items`` (List[PIL.Image.Image | str])

    Writes:
        - ``raw_results`` (List[str])  — same order as ``content_items``
        - ``model_instance``           — reference to loaded model
    """

    def __init__(self, name: str = "inference") -> None:
        super().__init__(name=name)

    def validate_input(self, context: Dict[str, Any]) -> bool:
        """Require non-empty content_items and a model_id."""
        return (
            context.get("content_items") is not None
            and len(context.get("content_items", [])) > 0
            and context.get("model_id") is not None
        )

    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Load the model and fan out inference over content items."""
        # Lazy import to avoid circular deps and heavy module loading.
        from src.ingestion.processor import get_cached_model

        model_id: str = context["model_id"]
        api_keys = context.get("api_keys")
        content_items: List[Any] = context["content_items"]

        model = await get_cached_model(model_id, api_keys)
        context["model_instance"] = model

        semaphore = await get_registry().get(model_id)
        cache = get_cache()
        prompt = get_prompts().get(
            doc_subtype=context.get("document_subtype"),
            region_type="page",
        )

        tasks = [
            self._process_one(idx, item, model, model_id, prompt, semaphore, cache)
            for idx, item in enumerate(content_items)
        ]
        results: List[str] = await asyncio.gather(*tasks)

        context["raw_results"] = results
        logger.info(
            "Inference stage: %d items, cache hits=%d misses=%d",
            len(results),
            cache.hits,
            cache.misses,
        )
        return context

    @staticmethod
    async def _process_one(
        idx: int,
        item: Any,
        model: Any,
        model_id: str,
        prompt: str,
        semaphore: asyncio.Semaphore,
        cache: InferenceResultCache,
    ) -> str:
        """Run inference on a single content item, gated by ``semaphore``.

        Office text passes through unchanged. Images are PNG-encoded, looked
        up in the cache, and only sent to the model on a cache miss. The
        sync ``model.process`` call is run in the default thread pool while
        holding the semaphore.
        """
        from PIL import Image

        if isinstance(item, str):
            return item

        if not isinstance(item, Image.Image):
            logger.warning(
                "Inference: skipping unsupported item type at %d: %s",
                idx,
                type(item).__name__,
            )
            return ""

        buf = io.BytesIO()
        item.save(buf, format="PNG")
        img_bytes = buf.getvalue()

        key = cache.make_key(img_bytes, prompt, model_id)
        cached = await cache.get(key)
        if cached is not None:
            logger.debug("Inference cache hit for item %d", idx)
            return cached

        async with semaphore:
            loop = asyncio.get_event_loop()
            raw = await loop.run_in_executor(
                None,
                lambda b=img_bytes, p=prompt: model.process(image=b, prompt=p),
            )
        content = raw.get("content", "") if isinstance(raw, dict) else ""
        await cache.set(key, content)
        return content
