"""Source-derived rent agreement terms, separate from reviewed classification."""

from datetime import date
from typing import Annotated, Literal

from pydantic import (
    Field,
    JsonValue,
    StringConstraints,
    TypeAdapter,
    field_validator,
    model_validator,
)

from ._base import _PaperSchema
from ._types import Currency, DecimalString, Identity, PositiveInteger, Text
from .installment_schedule import InstallmentSchedule
from .party_roles import PartyRoles, party_roles_json_schema
from .withholding_policy import WithholdingPolicy

_RENT_BASIS: TypeAdapter[str | None] = TypeAdapter(Identity | None)
_SourceNarrative = Annotated[
    str,
    StringConstraints(
        strict=True, strip_whitespace=True, min_length=1, max_length=24000, pattern=r"\S"
    ),
]


class RentAgreementSchema(_PaperSchema):
    """External PAPER.73 extraction terms with explicit unknown values.

    Monetary values use plain decimal strings, preserving precision in JSON.
    Fields describe document content; an approval record owns classification.
    """

    extensions: dict[str, JsonValue] = Field(
        default_factory=dict,
        max_length=128,
        description="Host-owned optional source attributes. When fixed_rent is extracted, also extract its source-supported pricing unit in fixed_rent_basis; omit it or use null if the source does not establish a basis. Do not infer a billing basis from installment timing. When extracting parties, preserve the legal landlord and tenant separately in party_roles, including exact source role designations and complete representation chains across pages. Extensions do not establish approval or classification.",
        json_schema_extra={
            "properties": {
                "fixed_rent_basis": _RENT_BASIS.json_schema(),
                "party_roles": party_roles_json_schema(),
            }
        },
    )

    vendor_name: Identity | None = Field(
        default=None,
        description="Legal landlord or rent supplier established by operative source role clauses and complete representation chains, not the tenant/customer, notary, attorney, or signatory acting on their behalf. Preserve parties separately in extensions.party_roles. Do not infer roles from first/second party order. Null if unknown or ambiguous.",
    )
    vendor_id: Identity | None = Field(
        default=None,
        description="External system vendor identifier only when explicitly present; never invent one from the landlord name.",
    )
    store_id: Identity | None = Field(
        default=None,
        description="External system store identifier only when explicitly present; a place name is not a store identifier.",
    )
    location: Text | None = Field(
        default=None,
        description="Location of the leased premises from the operative clause identifying the leased asset, including its article or section, rather than the first address on a cover sheet. Exclude the notary office and party correspondence addresses unless the contract explicitly identifies that same address as the leased asset. Preserve available locality details; null if unknown.",
    )
    contract_number: Identity | None = None
    lease_start_date: date | None = Field(
        default=None,
        description="Stated contractual rental start, ISO date; keep handover and rent-free fit-out dates separately in extensions. This field does not decide accounting commencement.",
    )
    lease_end_date: date | None = Field(
        default=None,
        description="Stated initial rental end, ISO date; do not add an unexercised renewal option or post-expiry dismantling grace period.",
    )
    lease_duration_months: PositiveInteger | None = Field(
        default=None,
        description="Stated initial rental duration in whole months, excluding an unexercised renewal option; null if not determinable. Does not decide approved accounting classification.",
    )
    payment_schedule: _SourceNarrative | None = Field(
        default=None,
        json_schema_extra={"x-source-text": True},
        description="For every cash installment, preserve the amount, due date, and ALL source payment prerequisites and contingent triggers: required signatures, handover or other events, receipt of complete invoices or tax/identity documents, and their submission deadlines. Preserve AND versus OR conditions, working versus calendar days, before versus after, and alternative dates. Do not reduce a conditional obligation to only a date or omit a document completeness requirement. Annual pricing does not imply annual installments; null if unknown.",
    )
    rent_type: Literal["fixed", "revenue_share", "mixed"] | None = None
    currency: Currency | None = Field(
        default=None,
        description="Three-letter ISO currency supported by the source, for example IDR for rupiah; null if unknown.",
    )
    fixed_rent: DecimalString | None = Field(
        default=None,
        description="Stated fixed rent price as a plain decimal string. Whenever extracting this amount, also extract the original source-supported pricing unit in extensions.fixed_rent_basis (for example annual, monthly, or whole_term). Do not invent an unknown basis, substitute a cash installment, or silently recalculate source discrepancies. Preserve installments separately in payment_schedule or host-defined extensions.",
    )
    revenue_share_rate: DecimalString | None = Field(
        default=None,
        description="Decimal fraction of revenue, for example 0.05 for 5%; null if the rate cannot be determined.",
    )
    minimum_guaranteed_payment: DecimalString | None = None
    renewal_terms: _SourceNarrative | None = Field(
        default=None,
        json_schema_extra={"x-source-text": True},
        description="Preserve ALL stated renewal conditions: option duration, notice lead time and required form (including written notice when stated), mutually agreed price or price negotiation, and any required separate agreement or addendum. Do not reduce a contingent renewal to its duration, omit agreement conditions, or assume automatic exercise or accounting certainty.",
    )
    other_key_terms: tuple[_SourceNarrative, ...] = Field(
        default=(),
        json_schema_extra={"x-source-text": True},
        max_length=128,
        description="Other source terms such as separate deposits, fit-out, termination, and restoration. For termination preserve each distinct ground with ALL its qualifying conditions, AND versus OR conjunctions, required notice and cure periods, remedies, refunds, exceptions, and cross-references. Keep each remedy or refund tied to its own stated ground and prerequisites; do not substitute generic breach wording or treat a conditional remedy as applying universally. Preserve complete relevant clauses in the source language rather than shortened summaries. Distinguish deposits from rent payments and include conditions governing their return.",
    )
    bank_account: Identity | None = Field(
        default=None,
        description="Landlord rent payment account as a string, preserving leading zeros; exclude tenant refund accounts and leave null if ambiguous.",
    )
    installment_schedule: InstallmentSchedule | None = Field(
        default=None,
        description="Optional explicit cash installments with stable IDs, gross amounts and reviewed allocation coverage. This structured schedule does not establish approval, infer invoice service periods, or prove payment prerequisites fulfilled. Leave null when not supplied.",
    )
    withholding_policy: WithholdingPolicy | None = Field(
        default=None,
        description="Optional externally reviewed withholding rate and rounding policy on gross rent, effective only through agreement approval. Never infer tax law or invent a policy from a document label; preserve its source reference.",
    )

    @field_validator("extensions")
    @classmethod
    def _validate_extensions(cls, value: dict[str, JsonValue]) -> dict[str, JsonValue]:
        normalized = dict(value)
        if "fixed_rent_basis" in normalized:
            normalized["fixed_rent_basis"] = _RENT_BASIS.validate_python(
                normalized["fixed_rent_basis"]
            )
        if "party_roles" in normalized:
            normalized["party_roles"] = PartyRoles.model_validate(
                normalized["party_roles"]
            ).model_dump(mode="json")
        return normalized

    @model_validator(mode="after")
    def _validate_lease_dates(self) -> "RentAgreementSchema":
        if (
            self.lease_start_date is not None
            and self.lease_end_date is not None
            and self.lease_end_date < self.lease_start_date
        ):
            raise ValueError("Lease end precedes its start.")
        return self
