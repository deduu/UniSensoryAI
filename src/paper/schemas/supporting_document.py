"""External PAPER.ID supporting attachment data contract."""

from datetime import date

from ._base import _PaperSchema
from ._types import Currency, DecimalString, Identity, Text


class SupportingDocumentSchema(_PaperSchema):
    """Extract supporting document identities and source-derived relationships."""

    document_type: Identity | None = None
    reference_number: Identity | None = None
    document_date: date | None = None
    invoice_number: Identity | None = None
    contract_number: Identity | None = None
    vendor_name: Identity | None = None
    vendor_id: Identity | None = None
    store_id: Identity | None = None
    location: Text | None = None
    currency: Currency | None = None
    total: DecimalString | None = None
    description: Text | None = None
