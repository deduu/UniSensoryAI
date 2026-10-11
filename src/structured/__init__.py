"""Schema-driven structured extraction.

Pydantic models that constrain VLM output for known document subtypes
(invoice, receipt, form, generic report). The :class:`SchemaRegistry`
maps a document subtype to its schema; pipeline stages use it to ask the
model for JSON and validate the response.
"""

from .registry import SchemaRegistry, get_schema_registry
from .schemas import (
    FormField,
    FormSchema,
    GenericReportSchema,
    InvoiceLineItem,
    InvoiceSchema,
    ReceiptLineItem,
    ReceiptSchema,
    ReportSection,
)

__all__ = [
    "SchemaRegistry",
    "get_schema_registry",
    "InvoiceSchema",
    "InvoiceLineItem",
    "ReceiptSchema",
    "ReceiptLineItem",
    "FormSchema",
    "FormField",
    "GenericReportSchema",
    "ReportSection",
]
