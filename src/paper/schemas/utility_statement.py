"""External PAPER.ID utility statement data contract."""

from datetime import date

from ._base import _ServicePeriodSchema
from ._types import Currency, DecimalString, Identity, Text


class UtilityStatementSchema(_ServicePeriodSchema):
    """Extract utility service, usage, invoice, and payment references."""

    vendor_name: Identity | None = None
    vendor_id: Identity | None = None
    store_id: Identity | None = None
    location: Text | None = None
    invoice_number: Identity | None = None
    invoice_date: date | None = None
    contract_number: Identity | None = None
    utility_type: Identity | None = None
    account_number: Identity | None = None
    meter_number: Identity | None = None
    usage_quantity: DecimalString | None = None
    usage_unit: Identity | None = None
    currency: Currency | None = None
    subtotal: DecimalString | None = None
    tax_amount: DecimalString | None = None
    total: DecimalString | None = None
    bank_account: Identity | None = None
