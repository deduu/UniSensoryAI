"""Human allocation context kept separate from source-extracted service dates."""

from datetime import date

from pydantic import Field, model_validator

from src.paper.contracts._base import Identifier, Reason, _Contract


class ReconciliationReviewContext(_Contract):
    """Reviewed authority window for an advance installment, requiring AP review."""

    allocation_start: date
    allocation_end: date
    reason: Reason
    source_document_ids: tuple[Identifier, ...] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def _valid_allocation(self) -> "ReconciliationReviewContext":
        if self.allocation_end < self.allocation_start:
            raise ValueError("Reviewed allocation end precedes its start.")
        if len(set(self.source_document_ids)) != len(self.source_document_ids):
            raise ValueError("Allocation source references must be unique.")
        return self
