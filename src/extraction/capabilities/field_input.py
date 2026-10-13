"""Typed data for external-schema understanding."""

from src.extraction.contracts import DocumentResult, ExternalSchema
from src.extraction.contracts.base import _Contract


class FieldExtractionInput(_Contract):
    """Document evidence and portable schema, with a logical model profile."""

    document: DocumentResult
    external_schema: ExternalSchema
    model_profile: str = "fields"
