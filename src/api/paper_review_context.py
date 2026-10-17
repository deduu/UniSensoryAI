"""Validated UI guidance derived from trusted PAPER policies and actors."""

from typing import Literal

from src.paper.contracts._base import Identifier, _Contract


class PaperReviewContext(_Contract):
    """Current reviewer permissions and host-owned publication requirements.

    This read-only guidance does not grant authority or replace server checks
    when a reviewer submits an agreement approval or case disposition.
    """

    user_id: Identifier
    can_approve_agreements: bool
    can_decide_cases: bool
    agreement_required_fields: tuple[str, ...]
    agreement_required_fields_by_rent_type: dict[
        Literal["fixed", "revenue_share", "mixed"], tuple[str, ...]
    ]
    required_invoice_fields: tuple[Identifier, ...]
    required_tax_fields: tuple[Identifier, ...]
    required_documents: tuple[
        Literal["rent_invoice", "tax_invoice", "utility_statement", "supporting_document"], ...
    ]
    required_supporting_types: tuple[Identifier, ...]
    override_codes: tuple[Identifier, ...]
    policy_id: Identifier
    policy_version: Identifier
    enabled_rules: tuple[Literal["installments", "withholding"], ...] = ()
    allow_withholding_without_vat_invoice: bool = False
    withholding_required_supporting_types: tuple[Identifier, ...] = ()
    require_independent_agreement_approval: bool
    require_independent_case_approval: bool
