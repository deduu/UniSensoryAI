"""Independently injectable document and field capabilities."""

from .document import DocumentExtractionCapability
from .document_input import DocumentExtractionInput
from .field_input import FieldExtractionInput
from .fields import FieldExtractionCapability
from .source_text import SourceTextExtractionCapability
from .source_text_input import SourceTextExtractionInput

__all__ = [
    "DocumentExtractionCapability",
    "DocumentExtractionInput",
    "FieldExtractionCapability",
    "FieldExtractionInput",
    "SourceTextExtractionCapability",
    "SourceTextExtractionInput",
]
