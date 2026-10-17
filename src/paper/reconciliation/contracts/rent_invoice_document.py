"""Rent invoice fields qualified by an externally retained source document."""

from src.paper.schemas import RentInvoiceSchema

from ._base import _Document


class RentInvoiceDocument(_Document):
    """An invoice's source-derived fields, evidence, and extraction diagnostics."""

    fields: RentInvoiceSchema
