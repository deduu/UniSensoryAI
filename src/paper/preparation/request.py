"""Bounded case selection input; source values come exclusively from saved drafts."""

from pydantic import Field, PositiveInt, model_validator

from src.paper.association.selection import AssociationSelection
from src.paper.contracts import AgreementIdentity
from src.paper.contracts._base import Identifier, _Contract
from src.paper.reconciliation.contracts.review_context import ReconciliationReviewContext

from .reference import DocumentVersionReference


class PrepareCaseRequest(_Contract):
    """Select reviewed documents and an assigned contract without rewriting extraction."""

    identity: AgreementIdentity
    invoice: DocumentVersionReference
    tax_invoices: tuple[DocumentVersionReference, ...] = Field(default=(), max_length=99)
    utility_statements: tuple[DocumentVersionReference, ...] = Field(default=(), max_length=99)
    supporting_documents: tuple[DocumentVersionReference, ...] = Field(default=(), max_length=99)
    association: AssociationSelection | None = None
    review_context: ReconciliationReviewContext | None = None
    case_id: Identifier | None = None
    expected_version: PositiveInt | None = None

    @model_validator(mode="after")
    def _bounded_unique_selection(self) -> "PrepareCaseRequest":
        values = (
            self.invoice,
            *self.tax_invoices,
            *self.utility_statements,
            *self.supporting_documents,
        )
        if len(values) > 100:
            raise ValueError("A case selection exceeds its document budget.")
        ids = [item.draft_id for item in values]
        if len(set(ids)) != len(ids):
            raise ValueError("Select only one version of each document draft.")
        if (self.case_id is None) != (self.expected_version is None):
            raise ValueError("A case revision requires both case ID and expected version.")
        return self
