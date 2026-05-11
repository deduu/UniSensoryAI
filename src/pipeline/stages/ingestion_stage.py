"""Ingestion stage — validates file and detects document type and subtype."""

import logging
import re
from pathlib import Path
from typing import Any, Dict, Optional

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

# Filename keyword → document subtype. Order matters: the first hit wins, so
# more specific patterns come first.
_FILENAME_SUBTYPE_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\binv(oice)?\b|\bbill\b", re.IGNORECASE), "invoice"),
    (re.compile(r"\brec(eipt)?\b", re.IGNORECASE), "receipt"),
    (re.compile(r"\bform\b|\bapplication\b|\bquestionnaire\b", re.IGNORECASE), "form"),
    (re.compile(r"\breport\b|\bwhitepaper\b|\bmemo\b", re.IGNORECASE), "report"),
]


def _detect_subtype_from_filename(name: str) -> Optional[str]:
    """Return a document subtype hint from the file name, or ``None``."""
    for pattern, subtype in _FILENAME_SUBTYPE_PATTERNS:
        if pattern.search(name):
            return subtype
    return None


class IngestionStage(BasePipelineStage):
    """Validates that the file exists and detects its document type/subtype.

    Reads:
        - ``file_path``

    Writes:
        - ``document_type`` (str)
        - ``document_subtype`` (str | None) — used to pick per-type prompts
          in the inference stage. Heuristic only; downstream stages may refine.
    """

    def __init__(self, name: str = "ingestion") -> None:
        super().__init__(name=name)

    def validate_input(self, context: Dict[str, Any]) -> bool:
        """Require file_path to be present."""
        return "file_path" in context and context["file_path"] is not None

    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Validate file existence and detect type + subtype.

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
        # Do not overwrite an explicitly-supplied subtype (e.g. from the API).
        if not context.get("document_subtype"):
            context["document_subtype"] = _detect_subtype_from_filename(file_path.name)

        logger.info(
            "Ingestion stage: file=%s type=%s subtype=%s",
            file_path.name,
            doc_type,
            context.get("document_subtype"),
        )
        return context
