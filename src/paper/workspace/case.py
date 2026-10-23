"""Strict read-only PAPER workspace navigation contract."""

from datetime import datetime
from typing import Literal

from pydantic import Field

from src.paper.contracts import AgreementIdentity
from src.paper.contracts._base import Identifier

from ._base import _Summary
from .association import WorkspaceAssociation


class WorkspaceCase(_Summary):
    """Latest invoice case summary pointing to an exact durable revision."""

    case_id: Identifier
    version_number: int = Field(ge=1)
    identity: AgreementIdentity
    invoice_number: str | None
    vendor_name: str | None
    location: str | None
    status: Literal[
        "approved", "rejected", "duplicate", "matched", "incomplete", "mismatched", "needs_review"
    ]
    blocking_count: int = Field(ge=0)
    review_count: int = Field(ge=0)
    source_document_id: str
    association: WorkspaceAssociation | None = None
    created_at: datetime
    next_action: Literal[
        "view_case", "review_duplicate", "review_and_decide", "resolve_discrepancies"
    ]
