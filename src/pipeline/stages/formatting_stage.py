"""Formatting stage — aggregates raw results into final output dict."""

import logging
from typing import Any, Dict

from src.core.base import BasePipelineStage

logger = logging.getLogger(__name__)


class FormattingStage(BasePipelineStage):
    """Aggregates raw inference results into the final output dictionary.

    Reads:
        - ``raw_results`` (List[str])
        - ``content_items`` (for page count)

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
        """Aggregate results into final output.

        Args:
            context: Pipeline context dict.

        Returns:
            Updated context with ``formatted_output`` set.
        """
        raw_results = context["raw_results"]
        content_items = context.get("content_items", [])

        full_content = self.ITEM_SEPARATOR.join(raw_results)

        context["formatted_output"] = {
            "content": full_content,
            "page_count": len(content_items),
        }

        logger.info(
            "Formatting stage: aggregated %d items, %d chars total",
            len(raw_results),
            len(full_content),
        )
        return context
