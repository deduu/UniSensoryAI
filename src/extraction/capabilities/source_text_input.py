"""Validated input for optional literal source-text extraction."""

from src.extraction.contracts import DocumentResult, ExternalSchema, FieldExtractionResult
from src.extraction.contracts.base import _Contract


class SourceTextExtractionInput(_Contract):
    """The source, caller schema, and immutable initial field candidates."""

    document: DocumentResult
    external_schema: ExternalSchema
    fields: FieldExtractionResult
    model_profile: str = "fields"
