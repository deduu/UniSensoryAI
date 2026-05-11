"""Conversion stage — converts documents to processable content items."""

import logging
from typing import Any, Dict

from src.core.base import BasePipelineStage
from src.ingestion.converter import DocumentConverter
from src.ingestion.pdf_hybrid import PageBundle

logger = logging.getLogger(__name__)


class ConversionStage(BasePipelineStage):
    """Converts a document file into a list of content items.

    PDFs become a list of :class:`PageBundle` objects (hybrid extraction:
    native text layer + image regions). Raster images become a single-element
    list of ``PIL.Image``. Office files become a list of Markdown strings.

    Reads:
        - ``file_path``
        - ``start_page`` (optional)
        - ``end_page`` (optional)

    Writes:
        - ``content_items`` (List[PageBundle | PIL.Image.Image | str])
        - ``page_bundles`` (the same list when the doc is a PDF; ``None`` otherwise)
    """

    def __init__(self, name: str = "conversion") -> None:
        super().__init__(name=name)

    def validate_input(self, context: Dict[str, Any]) -> bool:
        """Require file_path to be present."""
        return "file_path" in context and context["file_path"] is not None

    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Convert document to content items.

        Returns:
            Updated context with ``content_items`` populated and, for PDFs,
            ``page_bundles`` set to the same list for downstream stages that
            want layout-aware access.

        Raises:
            ValueError: If conversion produces no content.
        """
        file_path = context["file_path"]
        start_page = context.get("start_page")
        end_page = context.get("end_page")

        logger.info("Conversion stage: converting %s", file_path)

        content_items = DocumentConverter.convert_hybrid(
            file_path,
            start_page=start_page,
            end_page=end_page,
        )

        if not content_items:
            raise ValueError("No processable content found in document.")

        context["content_items"] = content_items
        if any(isinstance(item, PageBundle) for item in content_items):
            context["page_bundles"] = content_items
        logger.info(
            "Conversion stage: produced %d content items",
            len(content_items),
        )
        return context
