"""Immutable terms and their effective interval."""

from datetime import date
from typing import Literal

from pydantic import Field, model_validator

from src.extraction.contracts import ExtractionIssue
from src.paper.schemas import RentAgreementSchema

from ._base import Identifier, Reason, _Contract
from .evidence import AgreementEvidence


class AgreementDraft(_Contract):
    """A new version's content, including explicit missing extracted terms."""

    schema_id: Literal["paper.rent_agreement"] = "paper.rent_agreement"
    schema_version: Literal["1"] = "1"
    terms: RentAgreementSchema
    effective_from: date
    effective_to: date
    source_document_ids: tuple[Identifier, ...] = Field(min_length=1, max_length=100)
    evidence: tuple[AgreementEvidence, ...] = Field(default=(), max_length=500)
    extraction_warnings: tuple[ExtractionIssue, ...] = Field(default=(), max_length=500)
    change_reason: Reason

    @model_validator(mode="after")
    def validate_snapshot(self) -> "AgreementDraft":
        """Validate periods and structural provenance without reading source files."""
        if self.effective_to < self.effective_from:
            raise ValueError("Effective end precedes effective start.")
        if len(set(self.source_document_ids)) != len(self.source_document_ids):
            raise ValueError("Source document IDs must be unique.")
        if any(item.document_id not in self.source_document_ids for item in self.evidence):
            raise ValueError("Evidence references a document outside this version.")
        if self.terms.lease_start_date and self.effective_from < self.terms.lease_start_date:
            raise ValueError("Effective period starts before the lease.")
        if self.terms.lease_end_date and self.effective_to > self.terms.lease_end_date:
            raise ValueError("Effective period ends after the lease.")
        return self
