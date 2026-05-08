"""Inference stage — loads model and runs VLM inference on content items."""

import asyncio
import io
import logging
from typing import Any, Dict, List

from src.core.base import BasePipelineStage

logger = logging.getLogger(__name__)


class InferenceStage(BasePipelineStage):
    """Loads the specified model and runs inference on each content item.

    For text items (Office files), the text is sent as a prompt with no image.
    For image items (PDF pages, raw images), the image is converted to bytes
    and sent alongside a generic extraction prompt.

    Reads:
        - ``model_id``
        - ``api_keys`` (optional)
        - ``content_items`` (List[PIL.Image.Image | str])

    Writes:
        - ``raw_results`` (List[str])
        - ``model_instance`` (reference to loaded model)
    """

    def __init__(self, name: str = "inference") -> None:
        super().__init__(name=name)

    def validate_input(self, context: Dict[str, Any]) -> bool:
        """Require content_items and model_id."""
        return (
            context.get("content_items") is not None
            and len(context.get("content_items", [])) > 0
            and context.get("model_id") is not None
        )

    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Load model and run inference.

        Args:
            context: Pipeline context dict.

        Returns:
            Updated context with ``raw_results`` and ``model_instance``.
        """
        # Lazy import to avoid circular deps and heavy module loading
        from src.ingestion.processor import get_cached_model

        model_id = context["model_id"]
        api_keys = context.get("api_keys")
        content_items = context["content_items"]

        # 1. Load model
        model = await get_cached_model(model_id, api_keys)
        context["model_instance"] = model

        # 2. Process each item
        results: List[str] = []
        loop = asyncio.get_event_loop()

        from PIL import Image

        for i, item in enumerate(content_items):
            logger.info("Inference: processing item %d/%d", i + 1, len(content_items))

            if isinstance(item, str):
                # Office converters already return extracted source text. Keep it intact
                # instead of asking the model for a lossy summary.
                results.append(item)

            elif isinstance(item, Image.Image):
                # Image path (PDF/images)
                prompt = (
                    "Transcribe every word, number, heading, table cell, label, and footnote "
                    "visible on this page exactly as written. Do not summarize, paraphrase, "
                    "interpret, or omit any content. Output the raw text only."
                )
                img_byte_arr = io.BytesIO()
                item.save(img_byte_arr, format="PNG")
                img_bytes = img_byte_arr.getvalue()

                page_result = await loop.run_in_executor(
                    None,
                    lambda b=img_bytes, p=prompt: model.process(image=b, prompt=p),
                )
                results.append(page_result.get("content", ""))

        context["raw_results"] = results
        logger.info("Inference stage: produced %d results", len(results))
        return context
