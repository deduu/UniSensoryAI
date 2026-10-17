"""Host-owned agreement publication policy."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.paper.schemas import RentAgreementSchema


def _default_rent_requirements() -> (
    dict[Literal["fixed", "revenue_share", "mixed"], tuple[str, ...]]
):
    return {
        "fixed": ("fixed_rent",),
        "revenue_share": ("revenue_share_rate",),
        "mixed": ("fixed_rent", "revenue_share_rate"),
    }


class AgreementMasterSettings(BaseModel):
    """Validated policy; does not contain model or accounting classification logic."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    required_agreement_fields: tuple[str, ...] = (
        "vendor_name",
        "store_id",
        "contract_number",
        "lease_start_date",
        "lease_end_date",
        "payment_schedule",
        "rent_type",
        "currency",
    )
    required_fields_by_rent_type: dict[
        Literal["fixed", "revenue_share", "mixed"], tuple[str, ...]
    ] = Field(default_factory=_default_rent_requirements)
    approver_roles: tuple[str, ...] = ("admin", "accountant", "ap_approver")
    require_independent_approval: bool = False
    repository_timeout_seconds: float = Field(default=15, gt=0, le=15)

    @model_validator(mode="after")
    def validate_policy(self) -> "AgreementMasterSettings":
        """Reject misspelled fields and empty authorization policies."""
        fields = (
            *self.required_agreement_fields,
            *(name for names in self.required_fields_by_rent_type.values() for name in names),
        )
        if not self.required_agreement_fields or any(
            name not in RentAgreementSchema.model_fields for name in fields
        ):
            raise ValueError("Required approval fields must name agreement terms.")
        if not self.approver_roles or any(not role.strip() for role in self.approver_roles):
            raise ValueError("At least one nonempty approver role is required.")
        return self
