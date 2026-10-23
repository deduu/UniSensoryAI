"""Optional immutable extraction metering; historical absence remains unknown."""

from decimal import Decimal
from typing import Literal

from pydantic import Field

from .base import _Contract
from .model_pricing import ModelPricing
from .model_usage_call import ModelUsageCall

_Coverage = Literal["complete", "partial", "unavailable"]
__all__ = ["ExtractionUsage", "ModelPricing"]


class ExtractionUsage(_Contract):
    """All attempted calls in one extraction run, with explicit coverage.

    Totals with partial coverage are known subtotals. An unavailable value is
    null; historical jobs must not be assigned zero usage or fabricated prices.
    Cost is always an estimate under retained host rates, never a billed amount.
    """

    version: Literal["1"] = "1"
    calls: tuple[ModelUsageCall, ...] = ()
    call_count: int = Field(ge=0)
    measured_call_count: int = Field(ge=0)
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)
    estimated_cost: Decimal | None = Field(default=None, ge=0)
    currency: str | None = None
    coverage: _Coverage
    cost_coverage: _Coverage
