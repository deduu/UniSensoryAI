"""Strict read-only PAPER workspace navigation contract."""

from datetime import datetime
from typing import Literal

from pydantic import Field

from src.paper.contracts._base import Identifier

from ._base import _Summary
from .link import WorkspaceLink


class WorkspaceDocument(_Summary):
    """Upload state and bounded exact workflow links without reading source artifacts."""

    job_id: Identifier
    filename: str
    schema_name: Literal["rent_agreement", "rent_invoice"]
    status: Literal["pending", "processing", "completed", "failed"]
    document_id: str | None
    archived: bool
    created_at: datetime
    warning_count: int = Field(default=0, ge=0)
    workflow_status: Literal[
        "processing",
        "extraction_failed",
        "ready_for_review",
        "agreement_draft",
        "agreement_approved",
        "invoice_case",
    ]
    workflow_links: tuple[WorkspaceLink, ...] = ()
    workflow_links_total: int = Field(default=0, ge=0)
    workflow_links_resolved: bool = False
    next_action: Literal[
        "wait_for_extraction",
        "retry_extraction",
        "review_agreement",
        "review_invoice",
        "open_agreement",
        "open_case",
    ]
