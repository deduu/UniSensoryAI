"""Pure reconciliation uses approved authority and exact decimal arithmetic."""

from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from src.extraction.contracts.issue import ExtractionIssue
from src.paper.contracts import AgreementDraft, AgreementIdentity, AgreementVersion, ApprovalRecord
from src.paper.errors import AgreementMasterError
from src.paper.reconciliation.composition import load_reconciliation_settings
from src.paper.reconciliation.contracts import (
    InvoicePackage,
    ReconciliationAssessment,
    ReconciliationFinding,
    RentInvoiceDocument,
    SupportingDocument,
    TaxInvoiceDocument,
)
from src.paper.reconciliation.engine import ReconciliationEngine
from src.paper.reconciliation.fingerprints import package_fingerprint, policy_fingerprint
from src.paper.reconciliation.ports.rule import BaseReconciliationRule
from src.paper.reconciliation.settings import ReconciliationSettings
from src.paper.schemas import (
    RentAgreementSchema,
    RentInvoiceSchema,
    SupportingDocumentSchema,
    TaxInvoiceSchema,
)


def _identity() -> AgreementIdentity:
    return AgreementIdentity(vendor_id="vendor-1", store_id="store-1", contract_number="contract-1")


def _agreement(**terms_overrides: object) -> AgreementVersion:
    terms = RentAgreementSchema.model_validate(
        {
            "vendor_id": "vendor-1",
            "vendor_name": "Vendor",
            "store_id": "store-1",
            "contract_number": "contract-1",
            "lease_start_date": "2026-01-01",
            "lease_end_date": "2026-12-31",
            "rent_type": "fixed",
            "currency": "IDR",
            "fixed_rent": "100.00",
            "bank_account": "001234",
            "payment_schedule": "monthly",
            "extensions": {"fixed_rent_basis": "monthly"},
            **terms_overrides,
        }
    )
    return AgreementVersion(
        agreement_id="agreement-1",
        tenant_id="tenant-1",
        version_number=1,
        identity=_identity(),
        draft=AgreementDraft(
            terms=terms,
            effective_from=date(2026, 1, 1),
            effective_to=date(2026, 12, 31),
            source_document_ids=("agreement-source",),
            change_reason="Original agreement",
        ),
        created_by="author",
        created_at=datetime.now(timezone.utc),
        approval=ApprovalRecord(
            classification="non_psak73",
            rule_set_id="manual",
            rule_set_version="1",
            reason="Reviewed",
            approved_by="approver",
            approved_at=datetime.now(timezone.utc),
        ),
    )


def _package(**invoice_overrides: object) -> InvoicePackage:
    invoice = RentInvoiceSchema.model_validate(
        {
            "vendor_id": "vendor-1",
            "store_id": "store-1",
            "contract_number": "contract-1",
            "invoice_number": "INV-001",
            "invoice_date": "2026-02-01",
            "currency": "IDR",
            "service_period_start": "2026-02-01",
            "service_period_end": "2026-02-28",
            "subtotal": "100.00",
            "tax_amount": "11.00",
            "total": "111.00",
            "bank_account": "001234",
            **invoice_overrides,
        }
    )
    return InvoicePackage(
        identity=_identity(),
        invoice=RentInvoiceDocument(source_document_id="rent-invoice", fields=invoice),
        tax_invoices=(
            TaxInvoiceDocument(
                source_document_id="tax-invoice",
                fields=TaxInvoiceSchema(
                    vendor_id="vendor-1",
                    store_id="store-1",
                    contract_number="contract-1",
                    invoice_number="INV-001",
                    tax_invoice_number="TAX-001",
                    tax_invoice_date=date(2026, 2, 1),
                    currency="IDR",
                    taxable_amount="100.00",
                    tax_amount="11.00",
                    total="111.00",
                ),
            ),
        ),
    )


def _assess(
    package: InvoicePackage, agreement: AgreementVersion | None = None
) -> ReconciliationAssessment:
    reference = agreement or _agreement()
    return ReconciliationEngine(ReconciliationSettings()).assess(
        package, agreement_start=reference, agreement_end=reference, tenant_id="tenant-1"
    )


def test_complete_package_matches_explicit_fixed_monthly_terms() -> None:
    result = _assess(_package())
    assert result.outcome == "matched"
    assert result.findings == ()
    assert result.agreement_reference is not None
    assert result.agreement_reference.version_number == 1
    assert result.agreement_reference.classification == "non_psak73"
    assert result.package_fingerprint == package_fingerprint(_package())
    assert result.policy_fingerprint == policy_fingerprint(ReconciliationSettings())


def test_missing_documents_and_fields_are_incomplete_before_discrepancies() -> None:
    package = _package(bank_account="other", total=None)
    package = InvoicePackage(identity=package.identity, invoice=package.invoice)
    result = _assess(package)
    assert result.outcome == "incomplete"
    assert {finding.code for finding in result.findings} >= {
        "missing_document",
        "missing_field",
        "bank_mismatch",
    }
    missing = [finding for finding in result.findings if finding.code == "missing_field"]
    assert missing[0].source_document_ids == ("rent-invoice",)
    assert all("001234" not in finding.message for finding in result.findings)


@pytest.mark.parametrize(
    "field,value,code",
    [
        ("vendor_id", "other", "identity_mismatch"),
        ("contract_number", "other", "identity_mismatch"),
        ("store_id", "other", "identity_mismatch"),
        ("currency", "USD", "currency_mismatch"),
        ("bank_account", "other", "bank_mismatch"),
        ("total", "110.00", "amount_mismatch"),
        ("subtotal", "99.00", "amount_mismatch"),
    ],
)
def test_invoice_discrepancies_are_blocking(field: str, value: str, code: str) -> None:
    result = _assess(_package(**{field: value}))
    assert result.outcome == "mismatched"
    assert code in {finding.code for finding in result.findings}


def test_decimal_arithmetic_preserves_large_values_without_float_rounding() -> None:
    amount = "1234567890123456789012345678901234567890.01"
    package = _package(
        subtotal=amount, tax_amount="0.09", total="1234567890123456789012345678901234567890.10"
    )
    tax = TaxInvoiceDocument(
        source_document_id="tax-invoice",
        fields=TaxInvoiceSchema.model_validate(
            {
                **package.tax_invoices[0].fields.model_dump(mode="json"),
                "taxable_amount": amount,
                "tax_amount": "0.09",
                "total": "1234567890123456789012345678901234567890.10",
            }
        ),
    )
    package = InvoicePackage(
        identity=package.identity, invoice=package.invoice, tax_invoices=(tax,)
    )
    result = _assess(package, _agreement(fixed_rent=amount))
    assert result.outcome == "matched"


def test_tiny_discrepancies_are_not_rounded_away_in_large_amounts() -> None:
    amount = "1" + "0" * 90 + ".00"
    package = _package(subtotal=amount, tax_amount="0.01", total=amount)
    result = _assess(package, _agreement(fixed_rent="1" + "0" * 90 + ".01"))
    findings = [finding for finding in result.findings if finding.code == "amount_mismatch"]
    assert result.outcome == "mismatched"
    assert any(finding.field_path == "/fields/total" for finding in findings)
    assert any(finding.field_path == "/invoice/fields/subtotal" for finding in findings)


class _SignatureRule(BaseReconciliationRule):
    @property
    def rule_id(self) -> str:
        return "host.signed_receipt"

    @property
    def rule_version(self) -> str:
        return "2"

    def evaluate(
        self,
        package: InvoicePackage,
        *,
        agreement: AgreementVersion | None,
        settings: ReconciliationSettings,
    ) -> tuple[ReconciliationFinding, ...]:
        return (
            ReconciliationFinding(
                code="missing_signature",
                severity="blocking",
                message="Signed receipt is required.",
                source_document_ids=(package.invoice.source_document_id,),
            ),
        )


def test_host_rules_bind_their_versions_without_changing_base_settings_fingerprint() -> None:
    engine = ReconciliationEngine(ReconciliationSettings(), extra_rules=(_SignatureRule(),))
    assert engine.settings_fingerprint == policy_fingerprint(ReconciliationSettings())
    assert engine.policy_fingerprint != engine.settings_fingerprint
    result = engine.assess(
        _package(), agreement_start=_agreement(), agreement_end=_agreement(), tenant_id="tenant-1"
    )
    assert result.outcome == "incomplete"
    assert result.findings[-1].code == "missing_signature"


def test_agreement_currency_must_be_available_even_if_other_terms_match() -> None:
    result = _assess(_package(), _agreement(currency=None))
    assert result.outcome == "incomplete"
    assert any(finding.field_path == "/agreement/terms/currency" for finding in result.findings)


def test_same_reference_cannot_have_different_authoritative_content() -> None:
    engine = ReconciliationEngine(ReconciliationSettings())
    with pytest.raises(AgreementMasterError) as error:
        engine.assess(
            _package(),
            agreement_start=_agreement(),
            agreement_end=_agreement(fixed_rent="999.00"),
            tenant_id="tenant-1",
        )
    assert error.value.code == "invalid_agreement"


def test_multiple_tax_documents_are_aggregated_without_assuming_tax_rates() -> None:
    package = _package()
    taxes = tuple(
        TaxInvoiceDocument(
            source_document_id=f"tax-{index}",
            fields=TaxInvoiceSchema.model_validate(
                {
                    **package.tax_invoices[0].fields.model_dump(mode="json"),
                    "tax_invoice_number": f"TAX-{index}",
                    "taxable_amount": taxable,
                    "tax_amount": tax,
                    "total": total,
                }
            ),
        )
        for index, taxable, tax, total in [
            (1, "60.00", "1.00", "61.00"),
            (2, "40.00", "10.00", "50.00"),
        ]
    )
    result = _assess(
        InvoicePackage(identity=package.identity, invoice=package.invoice, tax_invoices=taxes)
    )
    assert result.outcome == "matched"


@pytest.mark.parametrize(
    "override,code",
    [
        ({"extensions": {}}, "pricing_basis_unconfigured"),
        ({"rent_type": "revenue_share", "fixed_rent": None}, "unsupported_pricing"),
        ({"rent_type": "mixed"}, "unsupported_pricing"),
        ({"bank_account": None}, "bank_reference_missing"),
    ],
)
def test_unsupported_or_absent_authority_requires_review(
    override: dict[str, object], code: str
) -> None:
    result = _assess(_package(), _agreement(**override))
    assert result.outcome == "needs_review"
    assert code in {finding.code for finding in result.findings}


def test_partial_month_is_not_prorated_or_guessed() -> None:
    result = _assess(_package(service_period_start="2026-02-10"))
    assert result.outcome == "needs_review"
    assert "unsupported_pricing" in {finding.code for finding in result.findings}


def test_host_can_explicitly_choose_per_invoice_basis() -> None:
    result = ReconciliationEngine(ReconciliationSettings(fixed_rent_basis="per_invoice")).assess(
        _package(service_period_start="2026-02-10"),
        agreement_start=_agreement(extensions={}),
        agreement_end=_agreement(extensions={}),
        tenant_id="tenant-1",
    )
    assert result.outcome == "matched"


def test_missing_or_changed_agreement_cannot_establish_authority() -> None:
    engine = ReconciliationEngine(ReconciliationSettings())
    package = _package()
    missing = engine.assess(package, agreement_start=None, agreement_end=None, tenant_id="tenant-1")
    assert missing.outcome == "incomplete"
    changed = engine.assess(
        package,
        agreement_start=_agreement(),
        agreement_end=AgreementVersion.model_validate(
            {**_agreement().model_dump(), "version_number": 2}
        ),
        tenant_id="tenant-1",
    )
    assert changed.outcome == "incomplete"
    assert changed.agreement_reference is None


def test_service_period_must_be_covered_by_approved_effective_interval() -> None:
    result = _assess(_package(service_period_end="2027-02-28"))
    assert result.outcome == "incomplete"
    assert "agreement_coverage_missing" in {finding.code for finding in result.findings}


def test_wrong_tenant_authority_is_a_sanitized_adapter_error() -> None:
    agreement = AgreementVersion.model_validate(
        {**_agreement().model_dump(), "tenant_id": "other-tenant"}
    )
    with pytest.raises(AgreementMasterError) as error:
        _assess(_package(), agreement)
    assert error.value.code == "invalid_agreement"
    assert "other-tenant" not in str(error.value)


def test_extraction_warnings_are_retained_as_explicit_review_findings() -> None:
    package = _package()
    invoice = RentInvoiceDocument(
        source_document_id=package.invoice.source_document_id,
        fields=package.invoice.fields,
        warnings=(ExtractionIssue(code="unreadable", message="Source region could not be read"),),
    )
    result = _assess(
        InvoicePackage(
            identity=package.identity, invoice=invoice, tax_invoices=package.tax_invoices
        )
    )
    assert result.outcome == "needs_review"
    assert result.findings[0].code == "extraction_warnings"
    assert result.findings[0].source_document_ids == ("rent-invoice",)


def test_tax_references_and_amounts_match_primary_invoice() -> None:
    package = _package()
    wrong_tax = TaxInvoiceDocument(
        source_document_id="tax-invoice",
        fields=TaxInvoiceSchema.model_validate(
            {
                **package.tax_invoices[0].fields.model_dump(mode="json"),
                "invoice_number": "other",
                "currency": "USD",
                "tax_amount": "12.00",
                "service_period_start": "2026-03-01",
            }
        ),
    )
    result = _assess(
        InvoicePackage(
            identity=package.identity, invoice=package.invoice, tax_invoices=(wrong_tax,)
        )
    )
    assert result.outcome == "mismatched"
    assert {finding.code for finding in result.findings} >= {
        "invoice_reference_mismatch",
        "currency_mismatch",
        "amount_mismatch",
        "period_mismatch",
    }


def test_required_supporting_types_are_checked_without_an_llm() -> None:
    package = _package()
    engine = ReconciliationEngine(ReconciliationSettings(required_supporting_types=("receipt",)))
    incomplete = engine.assess(
        package, agreement_start=_agreement(), agreement_end=_agreement(), tenant_id="tenant-1"
    )
    assert incomplete.outcome == "incomplete"
    complete = InvoicePackage(
        identity=package.identity,
        invoice=package.invoice,
        tax_invoices=package.tax_invoices,
        supporting_documents=(
            SupportingDocument(
                source_document_id="receipt",
                fields=SupportingDocumentSchema(document_type="receipt"),
            ),
        ),
    )
    assert (
        engine.assess(
            complete, agreement_start=_agreement(), agreement_end=_agreement(), tenant_id="tenant-1"
        ).outcome
        == "matched"
    )


def test_valid_maximum_requirement_package_persists_all_structural_findings() -> None:
    settings = ReconciliationSettings(
        required_invoice_fields=tuple(RentInvoiceSchema.model_fields),
        required_tax_fields=tuple(TaxInvoiceSchema.model_fields),
        required_supporting_types=tuple(f"support-{number}" for number in range(64)),
    )
    warning = ExtractionIssue(code="unreadable", message="Source region could not be read")
    package = InvoicePackage(
        identity=_identity(),
        invoice=RentInvoiceDocument(
            source_document_id="invoice", fields=RentInvoiceSchema(), warnings=(warning,)
        ),
        tax_invoices=tuple(
            TaxInvoiceDocument(
                source_document_id=f"tax-{number}",
                fields=TaxInvoiceSchema(),
                warnings=(warning,),
            )
            for number in range(99)
        ),
    )
    assessment = ReconciliationEngine(settings).assess(
        package,
        agreement_start=None,
        agreement_end=None,
        tenant_id="tenant-1",
    )
    assert assessment.outcome == "incomplete"
    assert len(assessment.findings) > 2000
    assert sum(finding.code == "extraction_warnings" for finding in assessment.findings) == 100


class _UnboundedRule(_SignatureRule):
    def evaluate(
        self,
        package: InvoicePackage,
        *,
        agreement: AgreementVersion | None,
        settings: ReconciliationSettings,
    ) -> tuple[ReconciliationFinding, ...]:
        finding = super().evaluate(package, agreement=agreement, settings=settings)[0]
        return (finding,) * 101


def test_injected_rules_cannot_exhaust_the_persistable_findings_budget() -> None:
    engine = ReconciliationEngine(ReconciliationSettings(), extra_rules=(_UnboundedRule(),))
    with pytest.raises(AgreementMasterError) as error:
        engine.assess(
            _package(),
            agreement_start=_agreement(),
            agreement_end=_agreement(),
            tenant_id="tenant-1",
        )
    assert error.value.code == "invalid_configuration"


@pytest.mark.asyncio
async def test_packaged_configuration_matches_python_defaults_and_sanitizes_errors(
    tmp_path: Path,
) -> None:
    assert await load_reconciliation_settings() == ReconciliationSettings()
    path = tmp_path / "secret-configuration-path.yaml"
    path.write_text("override_codes: [agreement_missing]\n", encoding="utf-8")
    with pytest.raises(AgreementMasterError) as error:
        await load_reconciliation_settings(path)
    assert error.value.code == "invalid_configuration"
    assert "secret-configuration-path" not in str(error.value)
