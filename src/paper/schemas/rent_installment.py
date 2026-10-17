"""Explicit source or reviewed cash installment, separate from annual pricing."""

from datetime import date
from decimal import Decimal

from pydantic import Field, model_validator

from ._base import _PaperSchema
from ._types import DecimalString, Identity, Text


class RentInstallment(_PaperSchema):
    """One stable payment obligation with a reviewed authority coverage window.

    Coverage is allocation metadata, not an inferred invoice service period.
    Conditions remain source narrative and are never automatically fulfilled.
    """

    installment_id: Identity
    gross_amount: DecimalString
    coverage_start: date
    coverage_end: date
    conditions: tuple[Text, ...] = Field(default=(), max_length=32)

    @model_validator(mode="after")
    def _valid_installment(self) -> "RentInstallment":
        if Decimal(self.gross_amount) <= 0:
            raise ValueError("An installment gross amount must be positive.")
        if self.coverage_end < self.coverage_start:
            raise ValueError("Installment allocation coverage is reversed.")
        return self
