"""Formatting stage — aggregates results into the final output dict."""

import logging
from typing import Any, Dict, List

from src.core.base import BasePipelineStage

logger = logging.getLogger(__name__)


class FormattingStage(BasePipelineStage):
    """Aggregates raw inference results into the final output dictionary.

    Always emits ``content`` (the concatenated Markdown the frontend already
    reads) and ``page_count``. Additionally, when prior stages produced
    structured artifacts, they are passed through into the output dict so
    the persistence layer can write them into ``Document.content_chunks``:

    - ``chunks``: assembled by the enrichment stage. Falls back to a per-item
      shape derived from ``raw_results`` when enrichment did not run, so the
      basic pipeline still populates ``Document.content_chunks`` faithfully.
    - ``validation_errors``: surfaced verbatim for the API to display.

    Reads:
        - ``raw_results`` (List[str])
        - ``content_items`` (for page count)
        - ``content_chunks`` (optional, from EnrichmentStage)
        - ``validation_errors`` (optional)

    Writes:
        - ``formatted_output`` (Dict[str, Any])
    """

    ITEM_SEPARATOR = "\n\n--- ITEM BREAK ---\n\n"

    def __init__(self, name: str = "formatting") -> None:
        super().__init__(name=name)

    def validate_input(self, context: Dict[str, Any]) -> bool:
        """Require raw_results to be present and non-empty."""
        return (
            context.get("raw_results") is not None
            and len(context.get("raw_results", [])) > 0
        )

    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Aggregate into ``formatted_output``."""
        raw_results: List[str] = context["raw_results"]
        content_items = context.get("content_items") or []

        full_content = self.ITEM_SEPARATOR.join(raw_results)

        chunks = context.get("content_chunks")
        if not chunks:
            # Fallback: still populate Document.content_chunks per-page so the
            # column has useful data even when enrichment did not run.
            chunks = [
                {"page": idx + 1, "type": "page", "content": text}
                for idx, text in enumerate(raw_results)
            ]

        output: Dict[str, Any] = {
            "content": full_content,
            "page_count": len(content_items),
            "chunks": chunks,
        }

        validation_errors = context.get("validation_errors") or []
        if validation_errors:
            output["validation_errors"] = validation_errors

        context["formatted_output"] = output
        logger.info(
            "formatting: aggregated %d items, %d chars, %d chunks, %d validation notes",
            len(raw_results),
            len(full_content),
            len(chunks),
            len(validation_errors),
        )
        return context
