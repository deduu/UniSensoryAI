"""Pydantic schemas for structured extraction.

Each schema describes the JSON shape we expect the VLM to produce for a
given document subtype. ``extra="forbid"`` and ``str_strip_whitespace``
discipline the model: extra keys raise, blank strings are normalised, and
required fields must be present. Numeric fields keep ``float`` typing so
the model can return "1234.56" as a string and Pydantic will coerce it.
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class _StrictModel(BaseModel):
    """Base for schemas: forbid unknown keys, strip whitespace, coerce types."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )


# ---------------------------------------------------------------------------
# Invoice
# ---------------------------------------------------------------------------


class InvoiceLineItem(_StrictModel):
    description: str = Field(min_length=1)
    quantity: Optional[float] = None
    unit_price: Optional[float] = None
    line_total: Optional[float] = None


class InvoiceSchema(_StrictModel):
    """Structured representation of an invoice."""

    vendor_name: str = Field(min_length=1)
    vendor_address: Optional[str] = None
    bill_to: Optional[str] = None
    invoice_number: str = Field(min_length=1)
    invoice_date: Optional[str] = None
    due_date: Optional[str] = None
    line_items: List[InvoiceLineItem] = Field(default_factory=list)
    subtotal: Optional[float] = None
    tax: Optional[float] = None
    total: float
    currency: Optional[str] = None


# ---------------------------------------------------------------------------
# Receipt
# ---------------------------------------------------------------------------


class ReceiptLineItem(_StrictModel):
    description: str = Field(min_length=1)
    price: Optional[float] = None


class ReceiptSchema(_StrictModel):
    """Structured representation of a receipt."""

    merchant: str = Field(min_length=1)
    address: Optional[str] = None
    date: Optional[str] = None
    time: Optional[str] = None
    line_items: List[ReceiptLineItem] = Field(default_factory=list)
    subtotal: Optional[float] = None
    tax: Optional[float] = None
    tip: Optional[float] = None
    total: float
    payment_method: Optional[str] = None
    currency: Optional[str] = None


# ---------------------------------------------------------------------------
# Form
# ---------------------------------------------------------------------------


class FormField(_StrictModel):
    label: str = Field(min_length=1)
    value: Optional[str] = None
    # For checkboxes / radio fields; if not a binary control, leave None.
    checked: Optional[bool] = None


class FormSchema(_StrictModel):
    """Structured representation of a fillable form."""

    title: Optional[str] = None
    fields: List[FormField] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Generic report
# ---------------------------------------------------------------------------


class ReportSection(_StrictModel):
    heading: str = Field(min_length=1)
    content: str = Field(min_length=1)


class GenericReportSchema(_StrictModel):
    """Fallback schema for documents without a more specific subtype."""

    title: Optional[str] = None
    sections: List[ReportSection] = Field(default_factory=list)
