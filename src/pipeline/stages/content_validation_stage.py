"""Content-validation stage — critic pass over VLM extractions.

For each PDF page that went through full-page VLM (scanned page fall-back),
ask the same model to compare the extracted Markdown against the source
image and report any missing or hallucinated text. Findings are appended
to ``validation_errors`` for the API to surface; they do not fail the job.

Text-layer-only pages and Office text pass through unchecked: there is no
VLM hallucination surface to validate. The critic is gated by the per-model
semaphore so it doesn't blow past concurrency limits.
"""

from __future__ import annotations

import asyncio
import io
import logging
from typing import Any, Dict, List

from PIL import Image

from src.core.base import BasePipelineStage
from src.inference.concurrency import get_registry
from src.ingestion.pdf_hybrid import PageBundle

logger = logging.getLogger(__name__)

_OK_TOKEN = "OK"

_CRITIC_PROMPT = (
    "You are auditing a Markdown extraction against its source page image. "
    "Compare them carefully. If the extraction is faithful to the image, reply "
    "with EXACTLY the two characters: OK. "
    "Otherwise, list each discrepancy on its own line in the form "
    "'MISSING: <text>' for content present in the image but absent from the "
    "extraction, or 'HALLUCINATED: <text>' for content in the extraction not "
    "supported by the image. Do not include any other commentary."
    "\n\n"
    "Extracted Markdown:\n"
    "---\n"
    "{extraction}\n"
    "---"
)


class ContentValidationStage(BasePipelineStage):
    """Run a per-page critic on full-page VLM extractions.

    Reads:
        - ``page_bundles`` (Optional[List[PageBundle]])
        - ``raw_results`` (List[str])
        - ``model_instance``
        - ``model_id``

    Writes:
        - ``validation_errors`` — appended with critic findings.
    """

    def __init__(self, name: str = "content_validation") -> None:
        super().__init__(name=name)

    def validate_input(self, context: Dict[str, Any]) -> bool:
        return (
            context.get("raw_results") is not None
            and context.get("model_instance") is not None
            and context.get("model_id") is not None
        )

    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        bundles = context.get("page_bundles") or []
        raw_results: List[str] = context.get("raw_results") or []
        if not bundles:
            logger.info("content_validation: no page_bundles, skipping")
            return context

        model = context["model_instance"]
        model_id: str = context["model_id"]
        semaphore = await get_registry().get(model_id)

        tasks = []
        targets: List[PageBundle] = []
        for idx, bundle in enumerate(bundles):
            if not isinstance(bundle, PageBundle):
                continue
            if not bundle.needs_full_page_vlm or bundle.full_page_image is None:
                continue
            extraction = raw_results[idx] if idx < len(raw_results) else ""
            if not extraction.strip():
                continue
            targets.append(bundle)
            tasks.append(
                self._critic_call(
                    bundle.full_page_image, extraction, model, semaphore
                )
            )

        if not tasks:
            logger.info("content_validation: nothing to audit")
            return context

        critic_outputs = await asyncio.gather(*tasks)

        errors: List[Dict[str, Any]] = context.get("validation_errors") or []
        for bundle, output in zip(targets, critic_outputs):
            stripped = (output or "").strip()
            if not stripped or stripped == _OK_TOKEN:
                continue
            errors.append(
                {
                    "stage": "content_validation",
                    "page": bundle.page_no,
                    "notes": stripped,
                }
            )
        context["validation_errors"] = errors

        logger.info(
            "content_validation: audited %d pages, %d had findings",
            len(tasks),
            sum(1 for o in critic_outputs if o and o.strip() and o.strip() != _OK_TOKEN),
        )
        return context

    @staticmethod
    async def _critic_call(
        image: Image.Image,
        extraction: str,
        model: Any,
        semaphore: asyncio.Semaphore,
    ) -> str:
        """Encode image, run the critic prompt against it, return raw text."""
        buf = io.BytesIO()
        image.save(buf, format="PNG")
        img_bytes = buf.getvalue()
        prompt = _CRITIC_PROMPT.format(extraction=extraction)

        async with semaphore:
            loop = asyncio.get_event_loop()
            try:
                raw = await loop.run_in_executor(
                    None,
                    lambda b=img_bytes, p=prompt: model.process(image=b, prompt=p),
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("content_validation: critic call failed: %s", exc)
                return ""

        return raw.get("content", "") if isinstance(raw, dict) else ""
