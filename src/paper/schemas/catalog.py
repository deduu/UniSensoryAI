"""Stable portable PAPER schema exports, without a model-provider dependency."""

from src.extraction.contracts import ExternalSchema

from ._base import _PaperSchema
from .rent_agreement import RentAgreementSchema
from .rent_invoice import RentInvoiceSchema
from .supporting_document import SupportingDocumentSchema
from .tax_invoice import TaxInvoiceSchema
from .utility_statement import UtilityStatementSchema

_SCHEMAS: dict[str, type[_PaperSchema]] = {
    "rent_agreement": RentAgreementSchema,
    "rent_invoice": RentInvoiceSchema,
    "tax_invoice": TaxInvoiceSchema,
    "utility_statement": UtilityStatementSchema,
    "supporting_document": SupportingDocumentSchema,
}
PAPER_SCHEMA_NAMES: tuple[str, ...] = tuple(_SCHEMAS)


def get_paper_schema(name: str, version: str = "1") -> ExternalSchema:
    """Export a fresh versioned schema for an existing extraction operation.

    Args:
        name: One of rent_agreement, rent_invoice, tax_invoice,
            utility_statement, or supporting_document.
        version: Explicit contract version; currently only version 1 is available.

    Returns:
        An independent JSON Schema definition carrying a stable PAPER identifier.

    Raises:
        ValueError: The requested name or version is unsupported.
    """
    if version != "1" or name not in _SCHEMAS:
        raise ValueError("Unsupported PAPER schema name or version.")
    return ExternalSchema.from_pydantic(_SCHEMAS[name], schema_id=f"paper.{name}", version=version)
