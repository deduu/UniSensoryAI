"""Private extraction model configuration without authoritative business decisions."""

from datetime import date

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator


class _PaperSchema(BaseModel):
    model_config = ConfigDict(
        extra="forbid", frozen=True, revalidate_instances="always", allow_inf_nan=False
    )

    extensions: dict[str, JsonValue] = Field(
        default_factory=dict,
        max_length=128,
        description="Host-owned optional attributes; extensions do not establish approval or classification.",
    )


class _ServicePeriodSchema(_PaperSchema):
    service_period_start: date | None = Field(
        default=None,
        description="First service date explicitly supported by the source, ISO calendar date; never infer it from invoice date, due date, or installment number. Null if unknown.",
    )
    service_period_end: date | None = Field(
        default=None,
        description="Last service date explicitly supported by the source, ISO calendar date; never infer it from invoice date or due date. Null if unknown.",
    )

    @model_validator(mode="after")
    def _validate_period(self) -> "_ServicePeriodSchema":
        if (
            self.service_period_start is not None
            and self.service_period_end is not None
            and self.service_period_end < self.service_period_start
        ):
            raise ValueError("Service period end precedes its start.")
        return self
