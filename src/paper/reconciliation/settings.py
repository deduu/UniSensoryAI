"""Validated host policy for model-independent document reconciliation."""

from typing import Annotated, Literal

from pydantic import ConfigDict, Field, StringConstraints, model_validator

from src.paper.contracts._base import Identifier, _Contract
from src.paper.readiness.requirement import FieldRequirement
from src.paper.schemas import RentInvoiceSchema, TaxInvoiceSchema

_OVERRIDABLE_CODES = frozenset(
    {
        "bank_mismatch",
        "bank_reference_missing",
        "amount_mismatch",
        "pricing_basis_unconfigured",
        "unsupported_pricing",
        "extraction_warnings",
        "approved_installment_allocation",
        "installment_conditions_review",
        "source_pricing_discrepancy",
    }
)


class ReconciliationSettings(_Contract):
    """Business requirements supplied by the embedding host, never by a model."""

    model_config = ConfigDict(extra="forbid", frozen=True, revalidate_instances="always")
    policy_id: Identifier = "paper.manual_reconciliation"
    policy_version: Identifier = "1"
    required_documents: tuple[
        Literal["rent_invoice", "tax_invoice", "utility_statement", "supporting_document"], ...
    ] = Field(default=("rent_invoice", "tax_invoice"), max_length=4)
    required_invoice_fields: tuple[Identifier, ...] = Field(
        default=(
            "vendor_id",
            "store_id",
            "contract_number",
            "invoice_number",
            "invoice_date",
            "currency",
            "service_period_start",
            "service_period_end",
            "subtotal",
            "tax_amount",
            "total",
            "bank_account",
        ),
        max_length=64,
    )
    required_tax_fields: tuple[Identifier, ...] = Field(
        default=(
            "vendor_id",
            "store_id",
            "invoice_number",
            "contract_number",
            "tax_invoice_number",
            "tax_invoice_date",
            "currency",
            "taxable_amount",
            "tax_amount",
            "total",
        ),
        max_length=64,
    )
    required_supporting_types: tuple[Identifier, ...] = Field(default=(), max_length=64)
    field_requirements: tuple[FieldRequirement, ...] = Field(default=(), max_length=128)
    fixed_rent_basis: Literal["approved_extension", "per_invoice", "monthly", "disabled"] = (
        "approved_extension"
    )
    enabled_rules: tuple[Literal["installments", "withholding"], ...] = ()
    allow_withholding_without_vat_invoice: bool = False
    withholding_required_supporting_types: tuple[Identifier, ...] = Field(
        default=("withholding_certificate",), min_length=1, max_length=16
    )
    amount_tolerance: Annotated[
        str, StringConstraints(pattern=r"^[0-9]+(?:\.[0-9]+)?$", max_length=64)
    ] = "0.00"
    override_codes: tuple[Identifier, ...] = (
        "bank_mismatch",
        "bank_reference_missing",
        "amount_mismatch",
        "pricing_basis_unconfigured",
        "unsupported_pricing",
        "extraction_warnings",
        "approved_installment_allocation",
        "installment_conditions_review",
        "source_pricing_discrepancy",
    )
    approver_roles: tuple[Identifier, ...] = ("admin", "accountant", "ap_approver")
    require_independent_approval: bool = False
    repository_timeout_seconds: float = Field(default=15.0, gt=0, le=15)

    @model_validator(mode="after")
    def _policy_requirements(self) -> "ReconciliationSettings":
        for values in (
            self.required_documents,
            self.required_invoice_fields,
            self.required_tax_fields,
            self.required_supporting_types,
            self.override_codes,
            self.approver_roles,
            self.enabled_rules,
            self.withholding_required_supporting_types,
        ):
            if len(set(values)) != len(values):
                raise ValueError("Policy requirements must not contain duplicates.")
        if not self.approver_roles:
            raise ValueError("At least one AP reviewer role is required.")
        field_keys = [(item.role, item.field) for item in self.field_requirements]
        if len(set(field_keys)) != len(field_keys):
            raise ValueError("A role and field may have only one explicit requirement.")
        if (
            self.allow_withholding_without_vat_invoice
            and not self.withholding_required_supporting_types
        ):
            raise ValueError(
                "Withholding document substitution requires a supporting evidence type."
            )
        if not set(self.required_invoice_fields).issubset(RentInvoiceSchema.model_fields):
            raise ValueError("Invoice requirements reference unsupported fields.")
        if not set(self.required_tax_fields).issubset(TaxInvoiceSchema.model_fields):
            raise ValueError("Tax requirements reference unsupported fields.")
        if not set(self.override_codes).issubset(_OVERRIDABLE_CODES):
            raise ValueError("Policy may only allow explicitly reviewable discrepancies.")
        return self
