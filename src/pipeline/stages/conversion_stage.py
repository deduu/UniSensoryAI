"""Conversion stage — converts documents to processable content items."""

import logging
from typing import Any, Dict

from src.core.base import BasePipelineStage
from src.ingestion.converter import DocumentConverter

logger = logging.getLogger(__name__)


class ConversionStage(BasePipelineStage):
    """Converts a document file into a list of content items.

    For PDFs and images, items are PIL Images.
    For Office files, items are text strings.

    Reads:
        - ``file_path``
        - ``start_page`` (optional)
        - ``end_page`` (optional)

    Writes:
        - ``content_items`` (List[PIL.Image.Image | str])
    """

    def __init__(self, name: str = "conversion") -> None:
        super().__init__(name=name)

    def validate_input(self, context: Dict[str, Any]) -> bool:
        """Require file_path to be present."""
        return "file_path" in context and context["file_path"] is not None

    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Convert document to content items.

        Args:
            context: Pipeline context dict.

        Returns:
            Updated context with ``content_items`` populated.

        Raises:
            ValueError: If conversion produces no content.
        """
        file_path = context["file_path"]
        start_page = context.get("start_page")
        end_page = context.get("end_page")

        logger.info("Conversion stage: converting %s", file_path)

        content_items = DocumentConverter.convert(
            file_path,
            start_page=start_page,
            end_page=end_page,
        )

        if not content_items:
            raise ValueError("No processable content found in document.")

        context["content_items"] = content_items
        logger.info(
            "Conversion stage: produced %d content items",
            len(content_items),
        )
        return context
