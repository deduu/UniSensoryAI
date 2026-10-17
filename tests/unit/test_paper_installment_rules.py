"""Installment allocations and withholding remain explicit, exact, and opt-in."""

from datetime import date, datetime, timezone

import pytest
from pydantic import ValidationError

from src.paper.contracts import AgreementDraft, AgreementIdentity, AgreementVersion, ApprovalRecord
from src.paper.reconciliation.composition import build_reconciliation_engine
from src.paper.reconciliation.contracts import (
    InvoicePackage,
    ReconciliationAssessment,
    SupportingDocument,
    TaxInvoiceDocument,
)
from src.paper.reconciliation.settings import ReconciliationSettings
from src.paper.schemas import (
    RentAgreementSchema,
    SupportingDocumentSchema,
    TaxInvoiceSchema,
)


def _schedule() -> dict[str, object]:
    return {
        "schedule_id": "advance-rent",
        "version": "1",
        "currency": "IDR",
        "total_gross": "5000",
        "source_reference": "agreement-source:article-3",
        "installments": [
            {
                "installment_id": name,
                "gross_amount": gross,
                "coverage_start": "2027-01-05",
                "coverage_end": "2032-01-04",
                "conditions": [],
            }
            for name, gross in (("stage-1", "3000"), ("stage-2", "2000"))
        ],
    }


def _policy(**overrides: object) -> dict[str, object]:
    return {
        "policy_id": "reviewed-withholding",
        "version": "1",
        "rate": "0.1",
        "rounding_mode": "down",
        "decimal_places": 0,
        "source_reference": "host-approved-policy:example",
        **overrides,
    }


def _agreement(**overrides: object) -> AgreementVersion:
    return AgreementVersion(
        agreement_id="agreement-1",
        tenant_id="tenant-1",
        version_number=1,
        identity=AgreementIdentity(vendor_id="vendor-1", store_id="store-1", contract_number="A-1"),
        draft=AgreementDraft(
            terms=RentAgreementSchema.model_validate(
                {
                    "currency": "IDR",
                    "rent_type": "fixed",
                    "fixed_rent": "1000",
                    "bank_account": "001234",
                    "lease_start_date": "2027-01-05",
                    "lease_end_date": "2032-01-04",
                    "extensions": {"fixed_rent_basis": "annual"},
                    "installment_schedule": _schedule(),
                    "withholding_policy": _policy(),
                    **overrides,
                }
            ),
            effective_from=date(2027, 1, 5),
            effective_to=date(2032, 1, 4),
            source_document_ids=("agreement-source",),
            change_reason="Human reviewed allocation and withholding configuration",
        ),
        created_by="author",
        created_at=datetime.now(timezone.utc),
        approval=ApprovalRecord(
            classification="psak73",
            rule_set_id="manual",
            rule_set_version="1",
            reason="Reviewed synthetic contract",
            approved_by="reviewer",
            approved_at=datetime.now(timezone.utc),
        ),
    )


def _package(**overrides: object) -> InvoicePackage:
    return InvoicePackage.model_validate(
        {
            "identity": {"vendor_id": "vendor-1", "store_id": "store-1", "contract_number": "A-1"},
            "invoice": {
                "source_document_id": "invoice-source",
                "fields": {
                    "invoice_number": "INV-1",
                    "invoice_date": "2026-10-08",
                    "currency": "IDR",
                    "bank_account": "001234",
                    "subtotal": "3000",
                    "tax_amount": "-300",
                    "vat_amount": "0",
                    "withholding_amount": "300",
                    "rounding_adjustment": "0",
                    "total": "2700",
                    "installment_id": "stage-1",
                    **overrides,
                },
            },
            "review_context": {
                "allocation_start": "2027-01-05",
                "allocation_end": "2032-01-04",
                "reason": "Explicit reviewed advance-rent allocation; invoice service dates unknown",
                "source_document_ids": ["agreement-source"],
            },
            "supporting_documents": [
                {
                    "source_document_id": "withholding-source",
                    "fields": {
                        "document_type": "withholding_certificate",
                        "reference_number": "CERT-1",
                        "document_date": "2026-10-08",
                        "invoice_number": "INV-1",
                        "vendor_id": "vendor-1",
                        "store_id": "store-1",
                        "contract_number": "A-1",
                        "currency": "IDR",
                        "total": overrides.get("withholding_amount", "300"),
                    },
                }
            ],
        }
    )


def _assess(
    package: InvoicePackage | None = None,
    agreement: AgreementVersion | None = None,
    **settings_overrides: object,
) -> ReconciliationAssessment:
    settings = ReconciliationSettings.model_validate(
        {
            "enabled_rules": ["installments", "withholding"],
            "required_documents": ["rent_invoice"],
            "required_invoice_fields": [
                "invoice_number",
                "currency",
                "subtotal",
                "tax_amount",
                "total",
            ],
            **settings_overrides,
        }
    )
    reference = agreement or _agreement()
    return build_reconciliation_engine(settings).assess(
        package or _package(),
        agreement_start=reference,
        agreement_end=reference,
        tenant_id="tenant-1",
    )


def _codes(result: ReconciliationAssessment) -> set[str]:
    return {finding.code for finding in result.findings}


def test_explicit_advance_allocation_uses_installment_and_keeps_source_period_unknown() -> None:
    package = _package()
    result = _assess(package)
    assert result.outcome == "needs_review"
    assert _codes(result) == {"approved_installment_allocation"}
    assert package.invoice.fields.service_period_start is None
    assert package.invoice.fields.service_period_end is None
    assert result.agreement_reference.version_number == 1


@pytest.mark.parametrize(
    "field,value,expected",
    [
        ("installment_id", None, "missing_installment_id"),
        ("installment_id", "stage-99", "installment_not_found"),
        ("subtotal", "1000", "installment_amount_mismatch"),
        ("currency", "USD", "currency_mismatch"),
        ("vat_amount", None, "missing_vat_amount"),
        ("withholding_amount", None, "missing_withholding_amount"),
        ("withholding_amount", "299", "withholding_amount_mismatch"),
        ("total", "2400", "net_payable_mismatch"),
        ("tax_amount", "0", "tax_component_mismatch"),
        ("rounding_adjustment", "100", "rounding_adjustment_exceeds_policy"),
    ],
)
def test_money_selection_and_policy_failures_block(
    field: str, value: object, expected: str
) -> None:
    result = _assess(_package(**{field: value}))
    assert expected in _codes(result)
    assert result.outcome in {"incomplete", "mismatched"}


def test_legacy_signed_tax_is_not_deducted_twice_and_is_optional_with_components() -> None:
    assert _codes(_assess()) == {"approved_installment_allocation"}
    assert _codes(_assess(_package(tax_amount=None))) == {"approved_installment_allocation"}


def test_vat_document_compares_gross_plus_vat_not_withheld_net() -> None:
    package = _package(vat_amount="330", tax_amount="30", total="3030")
    package = package.model_copy(
        update={
            "tax_invoices": (
                TaxInvoiceDocument(
                    source_document_id="vat-source",
                    fields=TaxInvoiceSchema(taxable_amount="3000", tax_amount="330", total="3330"),
                ),
            )
        }
    )
    assert _codes(_assess(package, required_tax_fields=())) == {"approved_installment_allocation"}
    bad = package.model_copy(
        update={
            "tax_invoices": (
                TaxInvoiceDocument(
                    source_document_id="vat-source",
                    fields=TaxInvoiceSchema(taxable_amount="3000", tax_amount="30", total="3030"),
                ),
            )
        }
    )
    assert "amount_mismatch" in _codes(_assess(bad, required_tax_fields=()))


def test_missing_withholding_policy_is_not_inferred_from_invoice_rate() -> None:
    assert "missing_withholding_policy" in _codes(
        _assess(agreement=_agreement(withholding_policy=None))
    )


def test_allocation_requires_approved_schedule_and_matching_source_references() -> None:
    assert "missing_installment_schedule" in _codes(
        _assess(agreement=_agreement(installment_schedule=None))
    )
    package = _package().model_dump(mode="json")
    package["review_context"]["source_document_ids"] = ["unrelated-source"]
    assert "allocation_source_mismatch" in _codes(_assess(InvoicePackage.model_validate(package)))


@pytest.mark.parametrize(
    "field,value",
    [
        ("allocation_start", "2027-01-06"),
        ("allocation_end", "2032-01-03"),
    ],
)
def test_allocation_must_match_selected_approved_installment(field: str, value: str) -> None:
    package = _package().model_dump(mode="json")
    package["review_context"][field] = value
    assert "installment_period_mismatch" in _codes(_assess(InvoicePackage.model_validate(package)))


def test_source_period_conflicts_cannot_be_hidden_by_review_context() -> None:
    result = _assess(_package(service_period_start="2027-02-01", service_period_end="2027-02-28"))
    assert "allocation_period_conflict" in _codes(result)


def test_no_context_and_no_source_period_remains_incomplete() -> None:
    package = _package().model_copy(update={"review_context": None})
    assert _assess(package).outcome == "incomplete"
    assert "missing_field" in _codes(_assess(package))


def test_payment_conditions_and_source_discrepancy_are_explicit_review_findings() -> None:
    schedule = _schedule()
    schedule["source_discrepancy_note"] = (
        "Stated annual amount times duration differs from stated total"
    )
    schedule["installments"][0]["conditions"] = [
        "Both parties signed AND complete invoice; alternative date applies"
    ]
    assert _codes(_assess(agreement=_agreement(installment_schedule=schedule))) == {
        "approved_installment_allocation",
        "installment_conditions_review",
        "source_pricing_discrepancy",
    }


@pytest.mark.parametrize("mutate", ["duplicate", "sum", "negative", "reversed"])
def test_approved_schedule_rejects_ambiguous_or_invalid_amounts(mutate: str) -> None:
    schedule = _schedule()
    if mutate == "duplicate":
        schedule["installments"][1]["installment_id"] = "stage-1"
    elif mutate == "sum":
        schedule["total_gross"] = "4999"
    elif mutate == "negative":
        schedule["installments"][0]["gross_amount"] = "-3000"
    else:
        schedule["installments"][0]["coverage_end"] = "2020-01-01"
    with pytest.raises(ValidationError):
        _agreement(installment_schedule=schedule)


@pytest.mark.parametrize(
    "field,value",
    [
        ("rate", "1.1"),
        ("rate", "-0.1"),
        ("rate", 0.1),
        ("decimal_places", 7),
        ("decimal_places", True),
        ("rounding_mode", "guess"),
        ("source_reference", ""),
    ],
)
def test_withholding_policy_requires_explicit_bounded_decimal_configuration(
    field: str, value: object
) -> None:
    with pytest.raises(ValidationError):
        _agreement(withholding_policy=_policy(**{field: value}))


@pytest.mark.parametrize(
    "rounding,expected", [("down", "300"), ("half_up", "301"), ("half_even", "300")]
)
def test_withholding_rounding_is_approved_and_not_float_based(rounding: str, expected: str) -> None:
    schedule = _schedule()
    schedule["installments"][0]["gross_amount"] = "3005"
    schedule["total_gross"] = "5005"
    total = str(3005 - int(expected))
    package = _package(
        subtotal="3005", withholding_amount=expected, tax_amount=f"-{expected}", total=total
    )
    result = _assess(
        package,
        _agreement(
            installment_schedule=schedule, withholding_policy=_policy(rounding_mode=rounding)
        ),
    )
    assert "withholding_amount_mismatch" not in _codes(result)


def test_configured_tolerance_applies_to_amount_but_not_selection_or_period() -> None:
    result = _assess(_package(subtotal="3000.01", total="2700.01"), amount_tolerance="0.01")
    assert _codes(result) == {"approved_installment_allocation"}
    assert "installment_not_found" in _codes(
        _assess(_package(installment_id="typo"), amount_tolerance="1000")
    )


def test_rule_versions_are_bound_to_policy_fingerprint_and_disabled_rules_fail_closed() -> None:
    configured = _assess()
    disabled = _assess(enabled_rules=())
    assert configured.policy_fingerprint != disabled.policy_fingerprint
    assert {"missing_installment_rule", "missing_withholding_rule"} <= _codes(disabled)


def test_structured_withholding_policy_also_works_without_installment_schedule() -> None:
    agreement = _agreement(
        installment_schedule=None, fixed_rent="3000", extensions={"fixed_rent_basis": "per_invoice"}
    )
    package = _package(
        installment_id=None, service_period_start="2027-01-05", service_period_end="2032-01-04"
    ).model_copy(update={"review_context": None})
    assert _assess(package, agreement).outcome == "matched"


def test_legacy_signed_adjustment_workflow_remains_unchanged() -> None:
    agreement = _agreement(
        installment_schedule=None,
        withholding_policy=None,
        fixed_rent="3000",
        extensions={"fixed_rent_basis": "per_invoice"},
    )
    package = _package(
        installment_id=None,
        vat_amount=None,
        withholding_amount=None,
        rounding_adjustment=None,
        service_period_start="2027-01-05",
        service_period_end="2032-01-04",
    ).model_copy(update={"review_context": None})
    assert _assess(package, agreement).outcome == "matched"


def test_missing_or_type_only_withholding_certificate_is_incomplete() -> None:
    package = _package().model_copy(update={"supporting_documents": ()})
    assert "missing_withholding_evidence" in _codes(_assess(package))
    package = _package().model_copy(
        update={
            "supporting_documents": (
                SupportingDocument(
                    source_document_id="stub",
                    fields=SupportingDocumentSchema(document_type="withholding_certificate"),
                ),
            )
        }
    )
    assert "missing_withholding_evidence_fields" in _codes(_assess(package))
    assert _assess(package).outcome == "incomplete"


def test_withholding_certificate_amounts_and_duplicate_references_block() -> None:
    package = _package().model_dump(mode="json")
    package["supporting_documents"][0]["fields"]["total"] = "299"
    assert "withholding_evidence_mismatch" in _codes(
        _assess(InvoicePackage.model_validate(package))
    )
    package = _package().model_dump(mode="json")
    second = {**package["supporting_documents"][0], "source_document_id": "second-source"}
    package["supporting_documents"].append(second)
    assert "duplicate_withholding_evidence" in _codes(
        _assess(InvoicePackage.model_validate(package))
    )


def test_vat_zero_can_substitute_actual_withholding_evidence_only_when_host_enabled() -> None:
    package = _package()
    assert "missing_document" in _codes(
        _assess(package, required_documents=("rent_invoice", "tax_invoice"))
    )
    enabled = _assess(
        package,
        required_documents=("rent_invoice", "tax_invoice"),
        allow_withholding_without_vat_invoice=True,
    )
    assert "missing_document" not in _codes(enabled)
    positive_vat = _package(vat_amount="330", tax_amount="30", total="3030")
    assert "missing_document" in _codes(
        _assess(
            positive_vat,
            required_documents=("rent_invoice", "tax_invoice"),
            allow_withholding_without_vat_invoice=True,
        )
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("vat_amount", "-1"),
        ("withholding_amount", "-1"),
        ("vat_amount", True),
        ("withholding_amount", 300),
    ],
)
def test_explicit_components_reject_negative_and_numeric_values(field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        _package(**{field: value})


def test_partial_source_dates_cannot_be_replaced_by_context() -> None:
    assert _assess(_package(service_period_start="2027-01-05")).outcome == "incomplete"


def test_adjustment_is_signed_and_bounded_by_approved_quantum() -> None:
    assert "amount_mismatch" not in _codes(
        _assess(_package(rounding_adjustment="-0.25", total="2699.75"))
    )
    assert "rounding_adjustment_exceeds_policy" in _codes(
        _assess(_package(rounding_adjustment="-1.01", total="2698.99"))
    )


def test_withholding_mismatch_is_not_hidden_by_large_host_tolerance() -> None:
    assert "withholding_amount_mismatch" in _codes(
        _assess(
            _package(withholding_amount="299", tax_amount="-299", total="2701"),
            amount_tolerance="1000",
        )
    )


def test_unknown_invoice_reference_cannot_accept_unrelated_withholding_evidence() -> None:
    agreement = _agreement(
        installment_schedule=None, fixed_rent="3000", extensions={"fixed_rent_basis": "per_invoice"}
    )
    package = _package(
        installment_id=None,
        invoice_number=None,
        currency=None,
        service_period_start="2027-01-05",
        service_period_end="2032-01-04",
    ).model_copy(update={"review_context": None})
    result = _assess(package, agreement, required_invoice_fields=("subtotal", "total"))
    assert {"missing_withholding_invoice_reference", "missing_component_currency"} <= _codes(result)
    assert result.outcome == "incomplete"


def test_missing_net_payable_cannot_match_when_host_field_requirements_are_relaxed() -> None:
    result = _assess(_package(total=None), required_invoice_fields=())
    assert "missing_component_total" in _codes(result)
    assert result.outcome == "incomplete"


@pytest.mark.parametrize("rent_type", [None, "mixed", "revenue_share"])
def test_variable_pricing_cannot_hide_behind_fixed_cash_installments(rent_type: str | None) -> None:
    assert "unsupported_installment_pricing" in _codes(
        _assess(agreement=_agreement(rent_type=rent_type))
    )


@pytest.mark.parametrize(
    "rules,missing",
    [(["installments"], "missing_withholding_rule"), (["withholding"], "missing_installment_rule")],
)
def test_partially_disabled_capabilities_fail_closed(rules: list[str], missing: str) -> None:
    assert missing in _codes(_assess(enabled_rules=rules))


def test_installment_coverage_outside_approved_authority_is_blocking() -> None:
    schedule = _schedule()
    schedule["installments"][1]["coverage_end"] = "2032-02-01"
    assert "installment_coverage_mismatch" in _codes(
        _assess(agreement=_agreement(installment_schedule=schedule))
    )


def test_maximum_agreement_source_count_does_not_overflow_findings() -> None:
    reference = _agreement().model_dump(mode="json")
    reference["draft"]["source_document_ids"] = [
        "agreement-source",
        *[f"source-{n}" for n in range(99)],
    ]
    result = _assess(agreement=AgreementVersion.model_validate(reference))
    assert all(len(finding.source_document_ids) <= 100 for finding in result.findings)


def test_hundred_digit_source_money_keeps_exact_decimal_arithmetic() -> None:
    gross = "1" + "0" * 98
    withheld = "1" + "0" * 97
    from decimal import Decimal, localcontext

    with localcontext() as context:
        context.prec = 256
        total = str(Decimal(gross) - Decimal(withheld))
        schedule = _schedule()
        schedule["installments"][0]["gross_amount"] = gross
        schedule["total_gross"] = str(Decimal(gross) + Decimal(2000))
    result = _assess(
        _package(
            subtotal=gross, withholding_amount=withheld, tax_amount=f"-{withheld}", total=total
        ),
        _agreement(installment_schedule=schedule),
    )
    assert _codes(result) == {"approved_installment_allocation"}


def test_rounding_cannot_turn_positive_rent_into_an_unsupported_credit() -> None:
    agreement = _agreement(
        installment_schedule=None,
        fixed_rent="0.6",
        extensions={"fixed_rent_basis": "per_invoice"},
        withholding_policy=_policy(rate="1", rounding_mode="half_up"),
    )
    package = _package(
        installment_id=None,
        subtotal="0.6",
        withholding_amount="1",
        tax_amount="-1",
        total="-0.4",
        service_period_start="2027-01-05",
        service_period_end="2032-01-04",
    ).model_copy(update={"review_context": None})
    assert {"unsupported_withholding_amount", "unsupported_negative_payable"} <= _codes(
        _assess(package, agreement)
    )


def test_retained_historical_installment_does_not_block_valid_amended_future_obligation() -> None:
    agreement = _agreement().model_dump(mode="json")
    agreement["version_number"] = 2
    agreement["draft"]["effective_from"] = "2028-01-01"
    items = agreement["draft"]["terms"]["installment_schedule"]["installments"]
    items[0]["coverage_end"] = "2027-12-31"
    items[1]["coverage_start"] = "2028-01-01"
    package = _package(
        installment_id="stage-2",
        subtotal="2000",
        withholding_amount="200",
        tax_amount="-200",
        total="1800",
    ).model_dump(mode="json")
    package["review_context"]["allocation_start"] = "2028-01-01"
    result = _assess(
        InvoicePackage.model_validate(package), AgreementVersion.model_validate(agreement)
    )
    assert _codes(result) == {"approved_installment_allocation"}
