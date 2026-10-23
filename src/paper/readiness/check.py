"""One inspectable readiness prerequisite without exposing source field values."""

from typing import Annotated, Literal

from pydantic import Field, StringConstraints

from src.paper.contracts._base import Identifier, _Contract

from ._schemas import DocumentRole


class ReadinessCheck(_Contract):
    """Explain field presence, selected documents, authority, or accounting guards."""

    kind: Literal["field", "document", "authority", "accounting"]
    role: DocumentRole | None = None
    field: Identifier | None = None
    field_path: str | None = Field(default=None, max_length=1000)
    label: Identifier
    requirement: Literal["required", "conditional", "optional"]
    status: Literal["satisfied", "missing", "not_applicable"]
    blocking: bool = False
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=5000)]
    source_document_ids: tuple[Identifier, ...] = Field(default=(), max_length=100)
    code: Identifier | None = None
