"""External document packages stay independent from providers and persistence."""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from src.paper.contracts import AgreementIdentity
from src.paper.reconciliation.contracts import (
    APDecision,
    APDecisionRecord,
    InvoiceCaseVersion,
    InvoicePackage,
    ReconciliationAssessment,
    RentInvoiceDocument,
    SupportingDocument,
)
from src.paper.reconciliation.fingerprints import (
    assessment_fingerprint,
    duplicate_key,
    package_fingerprint,
    policy_fingerprint,
)
from src.paper.reconciliation.settings import ReconciliationSettings
from src.paper.schemas import RentInvoiceSchema, SupportingDocumentSchema


def _package(invoice_number: str | None = "INV-001") -> InvoicePackage:
    return InvoicePackage(
        identity=AgreementIdentity(vendor_id="V-001", store_id="S-001", contract_number="C-001"),
        invoice=RentInvoiceDocument(
            source_document_id="doc-1", fields=RentInvoiceSchema(invoice_number=invoice_number)
        ),
    )


def test_unknown_fields_can_remain_in_an_incomplete_package() -> None:
    package = _package(None)
    assert package.invoice.fields.total is None
    assert package.tax_invoices == ()
    assert duplicate_key(package) is None


def test_package_source_ids_are_unique_across_document_roles() -> None:
    package = _package()
    with pytest.raises(ValidationError):
        InvoicePackage(
            identity=package.identity,
            invoice=package.invoice,
            supporting_documents=(
                SupportingDocument(source_document_id="doc-1", fields=SupportingDocumentSchema()),
            ),
        )


def test_package_has_a_total_document_budget() -> None:
    package = _package()
    with pytest.raises(ValidationError):
        InvoicePackage(
            identity=package.identity,
            invoice=package.invoice,
            supporting_documents=tuple(
                SupportingDocument(
                    source_document_id=f"attachment-{number}", fields=SupportingDocumentSchema()
                )
                for number in range(100)
            ),
        )


def test_fingerprints_bind_data_but_duplicate_identity_ignores_document_ids() -> None:
    package = _package()
    copied = InvoicePackage.model_validate(package.model_dump(mode="json"))
    assert package_fingerprint(package) == package_fingerprint(copied)
    altered = InvoicePackage.model_validate(
        {
            **package.model_dump(mode="json"),
            "invoice": {"source_document_id": "other-doc", "fields": {"invoice_number": "INV-001"}},
        }
    )
    assert duplicate_key(package) == duplicate_key(altered)
    assert package_fingerprint(package) != package_fingerprint(altered)
    assert duplicate_key(package) != duplicate_key(_package("INV-002"))


@pytest.mark.parametrize("digest", ["x" * 64, "a" * 63, "A" * 64])
def test_optional_host_content_digest_is_a_normalized_sha256(digest: str) -> None:
    with pytest.raises(ValidationError):
        RentInvoiceDocument(
            source_document_id="d", fields=RentInvoiceSchema(), content_sha256=digest
        )


def test_decision_rehydration_preserves_status_and_timestamps() -> None:
    package = _package()
    settings = ReconciliationSettings()
    assessment = ReconciliationAssessment(
        outcome="incomplete",
        policy_id=settings.policy_id,
        policy_version=settings.policy_version,
        policy_fingerprint=policy_fingerprint(settings),
        package_fingerprint=package_fingerprint(package),
    )
    case = InvoiceCaseVersion(
        case_id="case-1",
        tenant_id="tenant-1",
        version_number=1,
        package=package,
        assessment=assessment,
        created_by="author",
        created_at=datetime.now(timezone.utc),
        decision=APDecisionRecord(
            action="reject",
            reason="Missing supporting documents",
            decided_by="reviewer",
            decided_at=datetime.now(timezone.utc),
        ),
    )
    assert case.status == "rejected"
    assert InvoiceCaseVersion.model_validate(case.model_dump(mode="json")) == case
    assert assessment_fingerprint(assessment) == assessment_fingerprint(
        ReconciliationAssessment.model_validate(assessment.model_dump(mode="json"))
    )


def test_override_codes_are_unique_and_policy_cannot_allow_hard_blockers() -> None:
    with pytest.raises(ValidationError):
        APDecision(action="approve", reason="Reviewed", override_codes=("amount_mismatch",) * 2)
    for code in ("missing_field", "missing_document", "agreement_missing", "duplicate", "stale"):
        with pytest.raises(ValidationError):
            ReconciliationSettings(override_codes=(code,))


def test_reference_configuration_rejects_unknown_fields_and_unbounded_timeout() -> None:
    with pytest.raises(ValidationError):
        ReconciliationSettings(required_invoice_fields=("invented_amount",))
    with pytest.raises(ValidationError):
        ReconciliationSettings(repository_timeout_seconds=16)
    with pytest.raises(ValidationError):
        InvoicePackage.model_validate({**_package().model_dump(), "tenant_id": "external-tenant"})
