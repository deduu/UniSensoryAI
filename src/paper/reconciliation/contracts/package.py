"""Bounded document bundle belonging to a canonical agreement identity."""

from pydantic import Field, model_validator

from src.paper.association.confirmation import AssociationConfirmation
from src.paper.association.selection import AssociationSelection
from src.paper.contracts import AgreementIdentity
from src.paper.contracts._base import _Contract
from src.paper.preparation.selected_version import SelectedDocumentVersion

from .rent_invoice_document import RentInvoiceDocument
from .review_context import ReconciliationReviewContext
from .supporting_document import SupportingDocument
from .tax_invoice_document import TaxInvoiceDocument
from .utility_statement_document import UtilityStatementDocument


class InvoicePackage(_Contract):
    """An incomplete package is valid input, retaining all supplied diagnostics."""

    identity: AgreementIdentity
    invoice: RentInvoiceDocument
    association: AssociationConfirmation | AssociationSelection | None = None
    review_context: ReconciliationReviewContext | None = None
    tax_invoices: tuple[TaxInvoiceDocument, ...] = Field(default=(), max_length=99)
    utility_statements: tuple[UtilityStatementDocument, ...] = Field(default=(), max_length=99)
    supporting_documents: tuple[SupportingDocument, ...] = Field(default=(), max_length=99)
    document_draft_references: tuple[SelectedDocumentVersion, ...] = Field(default=(), max_length=100)

    @model_validator(mode="after")
    def _source_budget(self) -> "InvoicePackage":
        documents = (
            self.invoice,
            *self.tax_invoices,
            *self.utility_statements,
            *self.supporting_documents,
        )
        if len(documents) > 100:
            raise ValueError("An invoice package exceeds its document budget.")
        source_ids = [document.source_document_id for document in documents]
        if len(set(source_ids)) != len(source_ids):
            raise ValueError("Source document identifiers must be unique within a package.")
        return self
