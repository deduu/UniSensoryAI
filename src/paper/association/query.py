"""Bounded candidate requests containing source information without assigned IDs."""

from pydantic import Field

from src.paper.contracts._base import _Contract
from src.paper.reconciliation.contracts.rent_invoice_document import RentInvoiceDocument
from src.paper.reconciliation.contracts.review_context import ReconciliationReviewContext


class AssociationQuery(_Contract):
    """Search a tenant's agreement catalog without modifying the invoice."""

    invoice: RentInvoiceDocument
    review_context: ReconciliationReviewContext | None = None
    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=25, ge=1, le=100)
    search: str | None = Field(default=None, max_length=256)
