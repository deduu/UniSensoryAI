"""Private package primitives shared by external document envelopes."""

from typing import Annotated

from pydantic import Field, StringConstraints

from src.extraction.contracts.evidence import FieldEvidence
from src.extraction.contracts.issue import ExtractionIssue
from src.paper.contracts._base import Identifier, _Contract

Sha256 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]


class _Document(_Contract):
    source_document_id: Identifier
    evidence: tuple[FieldEvidence, ...] = Field(default=(), max_length=500)
    warnings: tuple[ExtractionIssue, ...] = Field(default=(), max_length=500)
    content_sha256: Sha256 | None = Field(
        default=None,
        description="Optional SHA-256 computed by the trusted source host, never by a model.",
    )
