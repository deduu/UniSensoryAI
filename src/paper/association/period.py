"""Keep source service dates distinct from explicit human allocation."""

from datetime import date

from src.paper.reconciliation.contracts.rent_invoice_document import RentInvoiceDocument
from src.paper.reconciliation.contracts.review_context import ReconciliationReviewContext


def association_period(
    invoice: RentInvoiceDocument, review_context: ReconciliationReviewContext | None = None
) -> tuple[date | None, date | None]:
    """Use human allocation only when both source service dates are absent."""
    first, last = invoice.fields.service_period_start, invoice.fields.service_period_end
    if first is None and last is None and review_context is not None:
        return review_context.allocation_start, review_context.allocation_end
    return first, last
