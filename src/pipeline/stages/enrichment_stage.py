"""Enrichment stage — assemble final ``content_chunks`` list.

This stage runs after inference + structured_output + content_validation
and produces a single ordered list of typed chunks that the formatting
stage attaches to the saved Document. The shape matches the existing
``content_chunks`` convention used by ``src/policy/service.py``.

Chunk shapes emitted:

- ``{"page": int, "type": "page", "content": str}`` — one per item from
  ``raw_results``. ``page`` is 1-indexed, sourced from ``PageBundle.page_no``
  when available, otherwise the item index plus one.
- ``{"page": None, "type": "structured", "schema_id": str, "content": dict}``
  — one per entry in ``structured_chunks``.
- ``{"page": int | None, "type": "validation", "content": dict}`` — one per
  entry in ``validation_errors`` so downstream surfaces can show critic notes
  inline. The original ``validation_errors`` list is preserved unchanged.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from src.core.base import BasePipelineStage
from src.ingestion.pdf_hybrid import PageBundle

logger = logging.getLogger(__name__)


class EnrichmentStage(BasePipelineStage):
    """Map raw results + structured + validation into ``content_chunks``."""

    def __init__(self, name: str = "enrichment") -> None:
        super().__init__(name=name)

    def validate_input(self, context: Dict[str, Any]) -> bool:
        return context.get("raw_results") is not None

    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        raw_results: List[str] = context.get("raw_results") or []
        bundles = context.get("page_bundles") or []
        structured_chunks = context.get("structured_chunks") or []
        validation_errors = context.get("validation_errors") or []

        chunks: List[Dict[str, Any]] = []

        for idx, text in enumerate(raw_results):
            page_no: Optional[int] = idx + 1
            if idx < len(bundles) and isinstance(bundles[idx], PageBundle):
                page_no = bundles[idx].page_no
            chunks.append(
                {
                    "page": page_no,
                    "type": "page",
                    "content": text,
                }
            )

        for entry in structured_chunks:
            chunks.append(
                {
                    "page": None,
                    "type": "structured",
                    "schema_id": entry.get("schema_id"),
                    "content": entry.get("content"),
                }
            )

        for err in validation_errors:
            if err.get("stage") != "content_validation":
                continue
            chunks.append(
                {
                    "page": err.get("page"),
                    "type": "validation",
                    "content": {
                        "stage": err.get("stage"),
                        "notes": err.get("notes"),
                    },
                }
            )

        context["content_chunks"] = chunks
        logger.info(
            "enrichment: produced %d chunks (page=%d structured=%d validation=%d)",
            len(chunks),
            len(raw_results),
            len(structured_chunks),
            sum(1 for c in chunks if c["type"] == "validation"),
        )
        return context
