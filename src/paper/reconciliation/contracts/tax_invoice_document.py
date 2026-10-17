"""Tax document fields qualified by an externally retained source document."""

from src.paper.schemas import TaxInvoiceSchema

from ._base import _Document


class TaxInvoiceDocument(_Document):
    """A tax document's fields without invented tax-rate or legal decisions."""

    fields: TaxInvoiceSchema
