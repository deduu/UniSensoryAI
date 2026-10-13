"""Typed input to extraction, separated from runtime collaborators."""

from src.extraction.contracts import DocumentResult, ExtractionOptions
from src.extraction.contracts.base import _Contract


class DocumentExtractionInput(_Contract):
    """Normalized document and requested representation."""

    document: DocumentResult
    options: ExtractionOptions
