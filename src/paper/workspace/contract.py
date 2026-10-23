"""Strict read-only PAPER workspace navigation contract."""

from datetime import datetime
from typing import Literal

from pydantic import Field

from src.paper.contracts import AgreementIdentity
from src.paper.contracts._base import Identifier

from ._base import _Summary


class WorkspaceContract(_Summary):
    """Latest agreement with separate prior approval and explicitly linked invoice counts."""

    agreement_id: Identifier
    version_number: int = Field(ge=1)
    identity: AgreementIdentity
    vendor_name: str | None
    location: str | None
    status: Literal["draft", "approved"]
    approved_version_number: int | None = Field(default=None, ge=1)
    linked_case_count: int = Field(ge=0)
    legacy_case_count: int = Field(ge=0)
    source_document_ids: tuple[str, ...]
    created_at: datetime
    next_action: Literal["review_agreement", "view_invoices"]
