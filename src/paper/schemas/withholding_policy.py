"""Reviewed withholding configuration; this contract does not infer tax law."""

from decimal import Decimal
from typing import Literal

from pydantic import Field, model_validator

from ._base import _PaperSchema
from ._types import DecimalString, Identity, Text


class WithholdingPolicy(_PaperSchema):
    """A versioned rate on gross rent with explicit decimal quantization policy."""

    policy_id: Identity
    version: Identity
    rate: DecimalString
    rounding_mode: Literal["down", "half_up", "half_even"]
    decimal_places: int = Field(strict=True, ge=0, le=6)
    source_reference: Text

    @model_validator(mode="after")
    def _bounded_rate(self) -> "WithholdingPolicy":
        if not Decimal(0) <= Decimal(self.rate) <= Decimal(1):
            raise ValueError("Withholding rate must be a decimal fraction between zero and one.")
        return self
