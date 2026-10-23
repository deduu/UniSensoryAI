"""Host-owned, model-bound pricing snapshot; no built-in provider prices."""

from datetime import date
from decimal import Decimal

from pydantic import Field

from .base import _Contract


class ModelPricing(_Contract):
    """Rates per million tokens, retained verbatim as an estimate's basis.

    Cached input is part of input tokens. A configured cached rate requires an
    explicitly reported cached-token count; it is never silently assumed zero.
    These rates describe an estimate, not a provider's actual invoiced charge.
    """

    pricing_id: str = Field(min_length=1, max_length=200)
    model_id: str = Field(min_length=1, max_length=300)
    allowed_response_model_ids: tuple[str, ...] = ()
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    input_per_million: Decimal = Field(ge=0)
    output_per_million: Decimal = Field(ge=0)
    cached_input_per_million: Decimal | None = Field(default=None, ge=0)
    source: str = Field(min_length=1, max_length=1000)
    as_of: date | None = None
