"""Persisted document extraction can survive a separate field-extraction failure."""

from typing import Literal

from pydantic import computed_field

from src.extraction.contracts import ExtractionIssue, ExtractionResult


class PaperExtractionResult(ExtractionResult):
    """Source content, business fields, and safe workflow diagnostics for review."""

    warnings: tuple[ExtractionIssue, ...] = ()

    @computed_field  # type: ignore[prop-decorator]
    @property
    def status(self) -> Literal["succeeded", "partial"]:
        """Report field failure or unverified evidence as incomplete review output."""
        if self.fields is None or self.warnings or self.document.status == "partial":
            return "partial"
        return self.fields.status
