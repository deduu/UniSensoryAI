"""Strict read-only PAPER workspace navigation contract."""

from typing import Literal

from pydantic import Field

from src.paper.contracts._base import Identifier

from ._base import _Summary


class WorkspaceQuery(_Summary):
    """Validated server-side search and page boundaries; no client tenant selection."""

    q: str = Field(default="", max_length=200)
    status: str | None = Field(default=None, max_length=32)
    agreement_id: Identifier | None = None
    job_id: Identifier | None = None
    workflow_status: (
        Literal[
            "processing",
            "extraction_failed",
            "ready_for_review",
            "agreement_draft",
            "agreement_approved",
            "invoice_case",
        ]
        | None
    ) = None
    association_kind: Literal["confirmed", "legacy_identity"] = "confirmed"
    archived: bool = False
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)
