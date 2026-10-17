"""Versioned cash schedule supplied through the agreement review boundary."""

from decimal import Decimal, localcontext

from pydantic import Field, model_validator

from ._base import _PaperSchema
from ._types import Currency, DecimalString, Identity, Text
from .rent_installment import RentInstallment


class InstallmentSchedule(_PaperSchema):
    """Explicit installments; no annual-price multiplication or due-date inference."""

    schedule_id: Identity
    version: Identity
    currency: Currency
    total_gross: DecimalString
    source_reference: Text
    source_discrepancy_note: Text | None = None
    installments: tuple[RentInstallment, ...] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def _unambiguous_schedule(self) -> "InstallmentSchedule":
        identifiers = [item.installment_id for item in self.installments]
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("Installment identifiers must be unique within a schedule.")
        with localcontext() as context:
            context.prec = 256
            total = sum((Decimal(item.gross_amount) for item in self.installments), Decimal(0))
            if total != Decimal(self.total_gross):
                raise ValueError("Schedule total must equal the exact sum of gross installments.")
        return self
