"""Safe usage metadata for one invocation of an injected generation provider."""

from decimal import Decimal
from typing import Annotated, Literal

from pydantic import Field

from .base import _Contract
from .model_pricing import ModelPricing

_Tokens = Annotated[int, Field(strict=True, ge=0)]


class ModelUsageCall(_Contract):
    """Measured provider counters and an optional configured price estimate."""

    sequence: int = Field(ge=1)
    profile: str
    provider: str
    model_id: str
    response_model_id: str | None = None
    purpose: Literal["ocr", "vision", "fields"]
    status: Literal["succeeded", "failed", "cancelled"]
    input_tokens: _Tokens | None = None
    output_tokens: _Tokens | None = None
    total_tokens: _Tokens | None = None
    cached_input_tokens: _Tokens | None = None
    estimated_cost: Decimal | None = Field(default=None, ge=0)
    currency: str | None = None
    pricing: ModelPricing | None = None
    error_code: str | None = None
