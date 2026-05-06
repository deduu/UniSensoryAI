"""Ingestion stage — validates file and detects document type."""

import logging
from pathlib import Path
from typing import Any, Dict

from src.core.base import BasePipelineStage

logger = logging.getLogger(__name__)

# Extension-to-type mapping
_EXT_TO_TYPE: Dict[str, str] = {
    ".pdf": "pdf",
    ".png": "image",
    ".jpg": "image",
    ".jpeg": "image",
    ".bmp": "image",
    ".tiff": "image",
    ".webp": "image",
    ".docx": "word",
    ".pptx": "powerpoint",
    ".xlsx": "excel",
}


class IngestionStage(BasePipelineStage):
    """Validates that the file exists and detects its document type.

    Reads:
        - ``file_path``

    Writes:
        - ``document_type`` (str)
    """

    def __init__(self, name: str = "ingestion") -> None:
        super().__init__(name=name)

    def validate_input(self, context: Dict[str, Any]) -> bool:
        """Require file_path to be present."""
        return "file_path" in context and context["file_path"] is not None

    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Validate file existence and detect type.

        Args:
            context: Pipeline context dict.

        Returns:
            Updated context with ``document_type`` set.

        Raises:
            FileNotFoundError: If the file does not exist.
            ValueError: If the file extension is unsupported.
        """
        file_path = Path(context["file_path"])

        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        ext = file_path.suffix.lower()
        doc_type = _EXT_TO_TYPE.get(ext)

        if doc_type is None:
            raise ValueError(f"Unsupported file extension: {ext}")

        context["document_type"] = doc_type
        logger.info(
            "Ingestion stage: file=%s, type=%s",
            file_path.name,
            doc_type,
        )
        return context
