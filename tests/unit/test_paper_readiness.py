"""Requirement policy and readiness are deterministic and enforced by matching."""

import hashlib
import json
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from src.paper.association.confirmation import AssociationConfirmation
from src.paper.readiness import ReadinessResult, evaluate
from src.paper.reconciliation.composition import build_reconciliation_engine
from src.paper.reconciliation.contracts import (
    InvoicePackage,
    ReconciliationAssessment,
    TaxInvoiceDocument,
)
from src.paper.reconciliation.engine import ReconciliationEngine
from src.paper.reconciliation.fingerprints import package_fingerprint, policy_fingerprint
from src.paper.reconciliation.settings import ReconciliationSettings
from tests.unit.test_paper_installment_rules import _agreement as _installment_agreement
from tests.unit.test_paper_installment_rules import _package as _installment_package
from tests.unit.test_paper_reconciliation import _agreement, _package


def _confirmed(package: InvoicePackage) -> InvoicePackage:
    from src.paper.association.fingerprints import invoice_fingerprint

    return InvoicePackage.model_validate(
        {
            **package.model_dump(),
            "association": AssociationConfirmation(
                agreement_id="agreement-1",
                version_number=1,
                reason="Reviewed source relationship",
                confirmed_by="reviewer",
                confirmed_at=datetime.now(timezone.utc),
                invoice_fingerprint=invoice_fingerprint(package.invoice, package.review_context),
                policy_id="association",
                policy_version="1",
            ),
        }
    )


def _evaluate(
    package: InvoicePackage, settings: ReconciliationSettings
) -> tuple[ReadinessResult, ReconciliationAssessment]:
    reference = _agreement()
    assessment = ReconciliationEngine(settings).assess(
        package, agreement_start=reference, agreement_end=reference, tenant_id="tenant-1"
    )
    return evaluate(package, assessment, settings), assessment


def _requirement(field: str, requirement: str = "required", **extra: object) -> dict[str, object]:
    return {
        "role": "rent_invoice",
        "field": field,
        "requirement": requirement,
        "reason": "Host payment review requirement",
        **extra,
    }


def test_empty_requirements_preserve_old_policy_and_package_fingerprints() -> None:
    settings = ReconciliationSettings()
    payload = settings.model_dump(mode="json", round_trip=True)
    payload.pop("field_requirements", None)
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    assert policy_fingerprint(settings) == hashlib.sha256(encoded.encode()).hexdigest()
    package = _package()
    snapshot = package.model_dump(mode="json", round_trip=True)
    snapshot.pop("association", None)
    snapshot.pop("document_draft_references", None)
    encoded = json.dumps(snapshot, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    assert package_fingerprint(package) == hashlib.sha256(encoded.encode()).hexdigest()


def test_required_field_is_enforced_by_engine_and_checklist() -> None:
    settings = ReconciliationSettings(field_requirements=(_requirement("due_date"),))
    result, assessment = _evaluate(_confirmed(_package()), settings)
    assert not result.ready
    assert any(item.field_path == "/invoice/fields/due_date" for item in assessment.findings)
    check = next(item for item in result.checks if item.field == "due_date")
    assert (check.requirement, check.status, check.blocking) == ("required", "missing", True)
    assert check.source_document_ids == ("rent-invoice",)
    assert result.policy_fingerprint == assessment.policy_fingerprint
    assert result.policy_fingerprint != policy_fingerprint(ReconciliationSettings())


def test_optional_can_waive_legacy_presence_but_not_service_coverage() -> None:
    settings = ReconciliationSettings(
        field_requirements=tuple(
            _requirement(field, "optional")
            for field in ("bank_account", "service_period_start", "service_period_end")
        )
    )
    result, assessment = _evaluate(_confirmed(_package(bank_account=None)), settings)
    assert result.ready
    assert assessment.outcome == "matched"
    check = next(item for item in result.checks if item.field == "bank_account")
    assert (check.status, check.blocking) == ("not_applicable", False)
    result, assessment = _evaluate(
        _confirmed(_package(service_period_start=None, service_period_end=None)), settings
    )
    assert not result.ready
    assert assessment.outcome == "incomplete"
    assert any(item.code == "missing_field" for item in assessment.findings)
    assert any(item.kind == "authority" and item.blocking for item in result.checks)
    coverage_guard = next(
        item
        for item in result.checks
        if item.kind == "accounting" and item.field == "service_period_start"
    )
    assert coverage_guard.label == "Service period start"
    assert coverage_guard.role == "rent_invoice"
    assert "cannot waive" in coverage_guard.reason


@pytest.mark.parametrize("amount,active", [("11.00", True), ("0.00", False)])
def test_conditional_requirement_uses_typed_equality(amount: str, active: bool) -> None:
    settings = ReconciliationSettings(
        field_requirements=(
            _requirement(
                "due_date",
                "conditional",
                when={
                    "role": "rent_invoice",
                    "field": "tax_amount",
                    "operator": "equals",
                    "value": "11.00",
                },
            ),
        )
    )
    result, assessment = _evaluate(_confirmed(_package(tax_amount=amount)), settings)
    check = next(item for item in result.checks if item.field == "due_date")
    assert (check.status == "missing") == active
    assert check.blocking == active
    assert (
        any(item.field_path == "/invoice/fields/due_date" for item in assessment.findings) == active
    )


@pytest.mark.parametrize("operator,active", [("present", True), ("absent", False)])
def test_condition_presence_does_not_treat_zero_as_missing(operator: str, active: bool) -> None:
    settings = ReconciliationSettings(
        field_requirements=(
            _requirement(
                "due_date",
                "conditional",
                when={"role": "rent_invoice", "field": "tax_amount", "operator": operator},
            ),
        )
    )
    result, _ = _evaluate(_confirmed(_package(tax_amount="0")), settings)
    assert next(item for item in result.checks if item.field == "due_date").blocking == active


def test_required_field_in_absent_optional_role_requires_that_document() -> None:
    settings = ReconciliationSettings(
        field_requirements=(
            {
                "role": "utility_statement",
                "field": "account_number",
                "requirement": "required",
                "reason": "Required utility account",
            },
        )
    )
    result, assessment = _evaluate(_confirmed(_package()), settings)
    assert not result.ready
    assert any(
        item.code == "missing_document" and item.field_path == "/utility_statement"
        for item in assessment.findings
    )
    missing = next(item for item in result.checks if item.field == "account_number")
    assert missing.blocking
    assert missing.reason == "Required utility account"


def test_readiness_permits_comparison_discrepancies_but_not_missing_authority() -> None:
    settings = ReconciliationSettings()
    package = _confirmed(_package(total="112.00"))
    result, assessment = _evaluate(package, settings)
    assert assessment.outcome == "mismatched"
    assert result.ready
    no_authority = ReconciliationEngine(settings).assess(
        package, agreement_start=None, agreement_end=None, tenant_id="tenant-1"
    )
    incomplete = evaluate(package, no_authority, settings)
    assert not incomplete.ready
    assert (
        len([item for item in incomplete.checks if item.kind == "authority" and item.blocking]) == 1
    )


def test_readiness_requires_confirmed_association_and_valid_snapshot_binding() -> None:
    settings = ReconciliationSettings()
    result, assessment = _evaluate(_package(), settings)
    assert not result.ready
    assert any(item.code == "contract_association_required" for item in result.checks)
    with pytest.raises(ValueError):
        evaluate(_package(total="999"), assessment, settings)


@pytest.mark.parametrize(
    "requirements",
    [
        (_requirement("missing_field_name"),),
        (_requirement("extensions"),),
        (_requirement("due_date"), _requirement("due_date", "optional")),
        (_requirement("due_date", "conditional"),),
        (
            _requirement(
                "due_date",
                "optional",
                when={"role": "rent_invoice", "field": "currency", "operator": "present"},
            ),
        ),
        (
            _requirement(
                "due_date",
                "conditional",
                when={
                    "role": "rent_invoice",
                    "field": "currency",
                    "operator": "equals",
                    "value": 12,
                },
            ),
        ),
        (
            _requirement(
                "due_date",
                "conditional",
                when={
                    "role": "rent_invoice",
                    "field": "invoice_date",
                    "operator": "equals",
                    "value": "not-a-date",
                },
            ),
        ),
        (
            _requirement(
                "due_date",
                "conditional",
                when={
                    "role": "rent_invoice",
                    "field": "currency",
                    "operator": "present",
                    "value": "IDR",
                },
            ),
        ),
        (
            _requirement(
                "due_date",
                "conditional",
                when={"role": "rent_invoice", "field": "currency", "operator": "equals"},
            ),
        ),
        (
            _requirement(
                "due_date",
                "conditional",
                when={"role": "rent_invoice", "field": "extensions", "operator": "absent"},
            ),
        ),
    ],
)
def test_invalid_requirements_fail_before_any_evaluation(
    requirements: tuple[dict[str, object], ...],
) -> None:
    with pytest.raises(ValidationError):
        ReconciliationSettings(field_requirements=requirements)


def test_requirement_budget_is_bounded() -> None:
    with pytest.raises(ValidationError):
        ReconciliationSettings(field_requirements=(_requirement("due_date"),) * 129)


def test_absent_optional_tax_role_does_not_activate_legacy_tax_field_requirements() -> None:
    original = _package()
    package = _confirmed(InvoicePackage(identity=original.identity, invoice=original.invoice))
    result, assessment = _evaluate(
        package, ReconciliationSettings(required_documents=("rent_invoice",))
    )
    assert result.ready
    assert assessment.outcome == "matched"


def test_explicit_tax_field_prevents_document_substitution_from_waiving_requirement() -> None:
    package = _confirmed(_installment_package())
    reference = _installment_agreement()
    settings = ReconciliationSettings(
        enabled_rules=("installments", "withholding"),
        allow_withholding_without_vat_invoice=True,
    )
    assessment = build_reconciliation_engine(settings).assess(
        package, agreement_start=reference, agreement_end=reference, tenant_id="tenant-1"
    )
    assert evaluate(package, assessment, settings).ready
    required = ReconciliationSettings.model_validate(
        {
            **settings.model_dump(),
            "field_requirements": [
                {
                    "role": "tax_invoice",
                    "field": "supplier_tax_id",
                    "requirement": "required",
                    "reason": "This host requires a tax invoice supplier identity",
                }
            ],
        }
    )
    assessment = build_reconciliation_engine(required).assess(
        package, agreement_start=reference, agreement_end=reference, tenant_id="tenant-1"
    )
    assert any(
        item.code == "missing_document" and item.field_path == "/tax_invoice"
        for item in assessment.findings
    )
    assert not evaluate(package, assessment, required).ready


def test_optional_components_never_disable_installed_accounting_guards() -> None:
    package = _confirmed(_installment_package(total=None))
    reference = _installment_agreement()
    settings = ReconciliationSettings(
        enabled_rules=("installments", "withholding"),
        required_documents=("rent_invoice",),
        field_requirements=(_requirement("total", "optional"),),
    )
    assessment = build_reconciliation_engine(settings).assess(
        package, agreement_start=reference, agreement_end=reference, tenant_id="tenant-1"
    )
    assert any(item.code == "missing_component_total" for item in assessment.findings)
    assert not evaluate(package, assessment, settings).ready


def test_decimal_condition_equality_cannot_be_bypassed_with_trailing_zero_scale() -> None:
    settings = ReconciliationSettings(
        field_requirements=(
            _requirement(
                "due_date",
                "conditional",
                when={
                    "role": "rent_invoice",
                    "field": "tax_amount",
                    "operator": "equals",
                    "value": "11",
                },
            ),
        )
    )
    result, assessment = _evaluate(_confirmed(_package(tax_amount="11.00")), settings)
    assert next(item for item in result.checks if item.field == "due_date").blocking
    assert any(item.field_path == "/invoice/fields/due_date" for item in assessment.findings)


def test_same_role_conditions_apply_independently_to_each_selected_document() -> None:
    package = _package()
    first = TaxInvoiceDocument.model_validate(
        {
            **package.tax_invoices[0].model_dump(),
            "fields": {
                **package.tax_invoices[0].fields.model_dump(),
                "supplier_tax_id": "supplier-tax",
            },
        }
    )
    second = TaxInvoiceDocument.model_validate(
        {
            **package.tax_invoices[0].model_dump(),
            "source_document_id": "second-tax",
        }
    )
    package = _confirmed(
        InvoicePackage.model_validate({**package.model_dump(), "tax_invoices": [first, second]})
    )
    settings = ReconciliationSettings(
        field_requirements=(
            {
                "role": "tax_invoice",
                "field": "buyer_tax_id",
                "requirement": "conditional",
                "reason": "Buyer identity needed when supplier identity is present",
                "when": {"role": "tax_invoice", "field": "supplier_tax_id", "operator": "present"},
            },
        )
    )
    result, assessment = _evaluate(package, settings)
    rows = [item for item in result.checks if item.field == "buyer_tax_id"]
    assert [(item.status, item.blocking) for item in rows] == [
        ("missing", True),
        ("not_applicable", False),
    ]
    paths = [item.field_path for item in assessment.findings if item.code == "missing_field"]
    assert paths == ["/tax_invoices/0/fields/buyer_tax_id"]


def test_maximum_host_reason_remains_valid_when_source_identity_is_assigned() -> None:
    settings = ReconciliationSettings(
        field_requirements=(_requirement("vendor_id", reason="R" * 4000),)
    )
    result, _ = _evaluate(_confirmed(_package(vendor_id=None)), settings)
    check = next(item for item in result.checks if item.field == "vendor_id")
    assert check.status == "satisfied"
    assert "source field remains absent" in check.reason
