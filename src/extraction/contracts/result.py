"""Combined result without provider-specific objects."""

from typing import Literal

from pydantic import computed_field

from .base import _Contract
from .document import DocumentResult
from .field_result import FieldExtractionResult


class ExtractionResult(_Contract):
    """Document output and optional externally specified business data."""

    schema_version: Literal["1"] = "1"
    document: DocumentResult
    fields: FieldExtractionResult | None = None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def status(self) -> Literal["succeeded", "partial"]:
        """Combine document and field completeness."""
        if self.document.status == "partial" or (self.fields and self.fields.status == "partial"):
            return "partial"
        return "succeeded"
