"""Bind association review to source fields, evidence, and reviewed allocation."""

import hashlib
import json

from src.paper.reconciliation.contracts.rent_invoice_document import RentInvoiceDocument
from src.paper.reconciliation.contracts.review_context import ReconciliationReviewContext


def invoice_fingerprint(
    invoice: RentInvoiceDocument, review_context: ReconciliationReviewContext | None = None
) -> str:
    """Hash association inputs independently of assigned master identifiers.

    Args:
        invoice: Source-derived fields, evidence, and diagnostics under review.
        review_context: Optional human allocation, kept outside source fields.

    Returns:
        Stable SHA-256 binding that becomes stale after source/allocation changes.
    """
    invoice = RentInvoiceDocument.model_validate(invoice)
    if review_context is not None:
        review_context = ReconciliationReviewContext.model_validate(review_context)
    payload = {
        "invoice": invoice.model_dump(mode="json", round_trip=True),
        "review_context": (
            review_context.model_dump(mode="json", round_trip=True) if review_context else None
        ),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()
