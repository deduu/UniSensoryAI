"""External PAPER.ID tax document data contract."""

from datetime import date

from ._base import _ServicePeriodSchema
from ._types import Currency, DecimalString, Identity, Text


class TaxInvoiceSchema(_ServicePeriodSchema):
    """Extract tax document identity and amounts without validating tax law."""

    vendor_name: Identity | None = None
    vendor_id: Identity | None = None
    supplier_tax_id: Identity | None = None
    buyer_name: Identity | None = None
    buyer_tax_id: Identity | None = None
    store_id: Identity | None = None
    location: Text | None = None
    tax_invoice_number: Identity | None = None
    tax_invoice_date: date | None = None
    invoice_number: Identity | None = None
    contract_number: Identity | None = None
    currency: Currency | None = None
    taxable_amount: DecimalString | None = None
    tax_amount: DecimalString | None = None
    total: DecimalString | None = None
    bank_account: Identity | None = None
