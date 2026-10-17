"""Source-qualified reconciliation finding without sensitive document values."""

from typing import Literal

from pydantic import Field

from src.paper.contracts._base import Identifier, Reason, _Contract


class ReconciliationFinding(_Contract):
    """A deterministic blocking discrepancy or a requirement for human review."""

    code: Identifier
    severity: Literal["blocking", "review"]
    message: Reason
    source_document_ids: tuple[Identifier, ...] = Field(default=(), max_length=100)
    field_path: str | None = Field(default=None, pattern=r"^/", max_length=512)
