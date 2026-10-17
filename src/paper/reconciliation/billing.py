"""Pure authority date selection without inventing source service periods."""

from datetime import date

from .contracts.package import InvoicePackage


def billing_period(package: InvoicePackage) -> tuple[date | None, date | None]:
    """Return source dates, or explicit allocation dates only when both are absent.

    Rule validation separately requires an approved matching installment. Partial
    source periods cannot be completed or replaced using review context.
    """
    fields = package.invoice.fields
    first, last = fields.service_period_start, fields.service_period_end
    if first is None and last is None and package.review_context is not None:
        return package.review_context.allocation_start, package.review_context.allocation_end
    return first, last
