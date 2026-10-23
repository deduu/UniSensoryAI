"""Immutable source draft snapshot with server-established review provenance."""

from typing import Literal

from pydantic import AwareDatetime, Field, model_validator
from typing_extensions import Self

from src.paper.contracts._base import Identifier, Reason

from .content import DocumentDraftContent


class DocumentDraftVersion(DocumentDraftContent):
    """An exact saved source version, never an AP or agreement approval."""

    draft_id: Identifier
    tenant_id: Identifier
    version_number: int = Field(ge=1, strict=True)
    status: Literal["draft", "reviewed"]
    created_by: Identifier
    created_at: AwareDatetime
    reason: Reason
    reviewed_by: Identifier | None = None
    reviewed_at: AwareDatetime | None = None

    @model_validator(mode="after")
    def _review_provenance(self) -> Self:
        if self.status == "reviewed":
            if self.reviewed_by != self.created_by or self.reviewed_at != self.created_at:
                raise ValueError("Reviewed drafts require current author and timestamp provenance.")
        elif self.reviewed_by is not None or self.reviewed_at is not None:
            raise ValueError("Unreviewed drafts cannot carry review provenance.")
        return self
