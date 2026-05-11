"""Inference stage — runs VLM inference on content items in parallel."""

import asyncio
import io
import logging
from typing import Any, Dict, List, Optional

from src.core.base import BasePipelineStage
from src.inference.concurrency import get_registry
from src.inference.result_cache import InferenceResultCache, get_cache
from src.ingestion.pdf_hybrid import PageBundle, RegionImage
from src.pipeline.prompts import PromptRegistry, get_prompts

logger = logging.getLogger(__name__)

_REGION_BREAK = "\n\n"


class InferenceStage(BasePipelineStage):
    """Loads the model and runs inference on each content item in parallel.

    Item handling:

    - ``str`` — Office-extracted Markdown. Passes through unchanged.
    - ``PageBundle`` — hybrid-extracted PDF page. The text layer passes through
      unchanged; each image region (figure/table) is sent to the VLM with a
      region-specific prompt. Scanned pages (``needs_full_page_vlm``) send the
      full-page image instead.
    - ``PIL.Image.Image`` — bare image. Sent to the VLM with the
      ``(doc_subtype, "page")`` prompt.

    Concurrency is bounded by a per-model ``asyncio.Semaphore``. Identical
    ``(image_bytes, prompt, model_id)`` inputs are served from
    ``InferenceResultCache`` and skip the model entirely.

    Reads:
        - ``model_id``
        - ``api_keys`` (optional)
        - ``content_items``
        - ``document_subtype`` (optional)

    Writes:
        - ``raw_results`` (List[str])   — one entry per input item, same order
        - ``model_instance``            — reference to loaded model
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
        doc_subtype: Optional[str] = context.get("document_subtype")

        model = await get_cached_model(model_id, api_keys)
        context["model_instance"] = model

        semaphore = await get_registry().get(model_id)
        cache = get_cache()
        prompts = get_prompts()

        tasks = [
            self._process_one(
                idx, item, model, model_id, doc_subtype, prompts, semaphore, cache
            )
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

    @classmethod
    async def _process_one(
        cls,
        idx: int,
        item: Any,
        model: Any,
        model_id: str,
        doc_subtype: Optional[str],
        prompts: PromptRegistry,
        semaphore: asyncio.Semaphore,
        cache: InferenceResultCache,
    ) -> str:
        """Run inference on one item, gated by ``semaphore``."""
        from PIL import Image

        if isinstance(item, str):
            return item

        if isinstance(item, PageBundle):
            return await cls._process_page_bundle(
                idx, item, model, model_id, doc_subtype, prompts, semaphore, cache
            )

        if isinstance(item, Image.Image):
            prompt = prompts.get(doc_subtype=doc_subtype, region_type="page")
            return await cls._run_vlm(
                item, prompt, model, model_id, semaphore, cache
            )

        logger.warning(
            "Inference: skipping unsupported item type at %d: %s",
            idx,
            type(item).__name__,
        )
        return ""

    @classmethod
    async def _process_page_bundle(
        cls,
        idx: int,
        bundle: PageBundle,
        model: Any,
        model_id: str,
        doc_subtype: Optional[str],
        prompts: PromptRegistry,
        semaphore: asyncio.Semaphore,
        cache: InferenceResultCache,
    ) -> str:
        """Combine native text and per-region VLM extractions for a PDF page."""
        if bundle.needs_full_page_vlm and bundle.full_page_image is not None:
            prompt = prompts.get(doc_subtype=doc_subtype, region_type="page")
            return await cls._run_vlm(
                bundle.full_page_image, prompt, model, model_id, semaphore, cache
            )

        parts: List[str] = []
        if bundle.text_layer.strip():
            parts.append(bundle.text_layer.strip())

        if bundle.image_regions:
            region_tasks = [
                cls._run_vlm(
                    region.image,
                    prompts.get(doc_subtype=doc_subtype, region_type=region.region_type),
                    model,
                    model_id,
                    semaphore,
                    cache,
                )
                for region in bundle.image_regions
            ]
            region_outputs = await asyncio.gather(*region_tasks)
            for region, output in zip(bundle.image_regions, region_outputs):
                if output.strip():
                    parts.append(f"<!-- {region.region_type} -->\n{output.strip()}")

        if not parts:
            logger.warning(
                "Inference: page bundle %d produced no content", bundle.page_no
            )
            return ""
        return _REGION_BREAK.join(parts)

    @staticmethod
    async def _run_vlm(
        image: Any,
        prompt: str,
        model: Any,
        model_id: str,
        semaphore: asyncio.Semaphore,
        cache: InferenceResultCache,
    ) -> str:
        """PNG-encode an image, consult the cache, and call the model if needed."""
        buf = io.BytesIO()
        image.save(buf, format="PNG")
        img_bytes = buf.getvalue()

        key = cache.make_key(img_bytes, prompt, model_id)
        cached = await cache.get(key)
        if cached is not None:
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
