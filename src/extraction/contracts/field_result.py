"""Validated external business data and evidence."""

from typing import Literal

from pydantic import JsonValue, computed_field

from .base import _Contract
from .evidence import FieldEvidence
from .issue import ExtractionIssue


class FieldExtractionResult(_Contract):
    """Schema-valid data with separately validated source evidence."""

    schema_id: str
    schema_version: str
    data: dict[str, JsonValue]
    evidence: tuple[FieldEvidence, ...] = ()
    warnings: tuple[ExtractionIssue, ...] = ()

    @computed_field  # type: ignore[prop-decorator]
    @property
    def status(self) -> Literal["succeeded", "partial"]:
        """Report evidence gaps or incomplete optional fields."""
        return "partial" if self.warnings else "succeeded"
