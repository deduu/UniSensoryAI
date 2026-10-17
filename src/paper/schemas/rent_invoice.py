"""External PAPER.ID rent invoice data contract."""

from datetime import date
from decimal import Decimal

from pydantic import Field, field_validator

from ._base import _ServicePeriodSchema
from ._types import Currency, DecimalString, Identity, Text


class RentInvoiceSchema(_ServicePeriodSchema):
    """Source-derived invoice identity, period, tax, and payment details.

    Unknown amounts remain null, and monetary JSON values remain strings.
    Negative values preserve adjustments rather than deciding their validity.
    """

    vendor_name: Identity | None = Field(
        default=None,
        description="Invoice issuer or rent supplier, not the billed customer; null if unknown.",
    )
    vendor_id: Identity | None = Field(
        default=None,
        description="External vendor identifier explicitly present in the source; do not invent one from a supplier name.",
    )
    store_id: Identity | None = Field(
        default=None,
        description="External store identifier explicitly present in the source; a locality name is not a store identifier.",
    )
    location: Text | None = Field(
        default=None,
        description="Leased premises or billed service location, including a location stated in the line description; exclude supplier postal and correspondence addresses.",
    )
    invoice_number: Identity | None = None
    invoice_date: date | None = Field(
        default=None, description="Invoice issue date, ISO calendar date; not a service period."
    )
    due_date: date | None = Field(
        default=None, description="Stated payment due date, ISO calendar date; null if unknown."
    )
    contract_number: Identity | None = Field(
        default=None,
        description="Agreement reference explicitly stated on the invoice; do not substitute the invoice number.",
    )
    currency: Currency | None = Field(
        default=None,
        description="Three-letter ISO currency supported by the source, for example IDR for Rp or rupiah; null if unknown.",
    )
    subtotal: DecimalString | None = Field(
        default=None,
        description="Gross amount before tax additions or withholding deductions, as a plain decimal string; null if not stated or determinable.",
    )
    tax_amount: DecimalString | None = Field(
        default=None,
        description="Signed source tax adjustment: additions positive and withholding deductions negative. Preserve printed rounding; do not treat PPh withholding as VAT or invent a tax invoice. Preserve separate labels, rates, and components in host-defined extensions when available; null if unknown.",
    )
    total: DecimalString | None = Field(
        default=None,
        description="Final amount payable after printed additions and deductions, as a plain decimal string; do not replace it with gross rent.",
    )
    bank_account: Identity | None = Field(
        default=None,
        description="Supplier payment account as a string preserving leading zeros; null if unknown or ambiguous.",
    )
    description: Text | None = Field(
        default=None,
        description="Source invoice line or purpose wording, preserving installment number and premises location when stated.",
    )
    installment_id: Identity | None = Field(
        default=None,
        description="Explicitly selected approved schedule obligation; never infer service dates from the installment ID.",
    )
    vat_amount: DecimalString | None = Field(
        default=None,
        description="Nonnegative VAT addition, distinct from withholding. Null is unknown; an explicit zero means reviewed no VAT addition.",
    )
    withholding_amount: DecimalString | None = Field(
        default=None,
        description="Nonnegative withholding deduction from gross rent. Separate from VAT; legacy signed tax_amount is a consistency check, never an additional deduction.",
    )
    rounding_adjustment: DecimalString | None = Field(
        default=None,
        description="Signed source payable adjustment only; bounded by an approved policy quantum, never an invoice-selected tolerance.",
    )

    @field_validator("vat_amount", "withholding_amount")
    @classmethod
    def _nonnegative_component(cls, value: str | None) -> str | None:
        if value is not None and Decimal(value) < 0:
            raise ValueError("Explicit VAT and withholding amounts must be nonnegative.")
        return value
