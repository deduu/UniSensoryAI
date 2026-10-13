"""Reusable extraction contracts; no application startup or ML model imports."""

from .composition import build_extraction_service
from .contracts import ExternalSchema, ExtractionOptions, PdfSource
from .errors import ExtractionError
from .service import ExtractionService

__all__ = [
    "ExternalSchema",
    "ExtractionError",
    "ExtractionOptions",
    "ExtractionService",
    "PdfSource",
    "build_extraction_service",
]
