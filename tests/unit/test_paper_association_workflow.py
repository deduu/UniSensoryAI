"""Confirmed master assignment must not manufacture source identity or provenance."""

import pytest

from src.paper.errors import AgreementMasterError
from src.paper.reconciliation.contracts import APDecision, InvoicePackage
from src.paper.reconciliation.engine import ReconciliationEngine
from src.paper.reconciliation.fingerprints import package_fingerprint
from src.paper.reconciliation.settings import ReconciliationSettings
from tests.unit.test_paper_case_workflow import _Setup, package, reference
from tests.unit.test_paper_case_workflow import setup as _workflow_setup

# Register the shared fixture locally; tests receive a fresh workflow for each case.
setup = _workflow_setup


def associated_package(*, conflict: bool = False) -> InvoicePackage:
    payload = package().model_dump(mode="json")
    payload["invoice"]["fields"].update(
        vendor_id="foreign-vendor" if conflict else None, store_id=None, contract_number=None
    )
    payload["association"] = {
        "agreement_id": "agreement-1",
        "version_number": 1,
        "reason": "Reviewed supplier and premises against the contract.",
    }
    return InvoicePackage.model_validate(payload)


def test_legacy_fingerprint_does_not_change_when_association_is_absent() -> None:
    assert package_fingerprint(package()) == (
        "7dc330283cc337ccc0418619920dceeb8d6a2a2e23998ef52e6cc55ededf727b"
    )


@pytest.mark.asyncio
async def test_confirmation_stamps_trusted_actor_and_preserves_missing_source_ids(
    setup: _Setup,
) -> None:
    service, repo, master, actor, _ = setup
    master.get_version.return_value = reference()
    pkg = associated_package()
    await service.create_case(actor=actor, package=pkg)
    saved = repo.create.await_args.kwargs
    assert saved["package"].invoice == pkg.invoice
    assert saved["package"].tax_invoices == pkg.tax_invoices
    confirmation = saved["package"].association
    assert confirmation.confirmed_by == actor.user_id
    assert confirmation.confirmed_at.tzinfo is not None
    assert confirmation.invoice_fingerprint
    assert saved["assessment"].outcome == "matched"
    assert not any(f.code == "missing_field" for f in saved["assessment"].findings)


@pytest.mark.asyncio
async def test_confirmation_never_hides_conflicting_extracted_identifiers(setup: _Setup) -> None:
    service, repo, master, actor, _ = setup
    master.get_version.return_value = reference()
    await service.create_case(actor=actor, package=associated_package(conflict=True))
    saved = repo.create.await_args.kwargs
    assert saved["package"].invoice.fields.vendor_id == "foreign-vendor"
    assert any(f.code == "identity_mismatch" for f in saved["assessment"].findings)


@pytest.mark.asyncio
async def test_forged_reviewer_fields_are_replaced_by_server_provenance(setup: _Setup) -> None:
    service, repo, master, actor, _ = setup
    master.get_version.return_value = reference()
    await service.create_case(actor=actor, package=associated_package())
    confirmed = repo.create.await_args.kwargs["package"].model_dump(mode="json")
    confirmed["association"]["confirmed_by"] = "forged-reviewer"
    confirmed["association"]["confirmed_at"] = "2000-01-01T00:00:00Z"
    await service.create_case(actor=actor, package=InvoicePackage.model_validate(confirmed))
    result = repo.create.await_args.kwargs["package"].association
    assert result.confirmed_by == actor.user_id
    assert result.confirmed_at.year != 2000


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid", ["draft", "foreign", "identity", "stale"])
async def test_confirmation_rejects_wrong_or_stale_authority_before_storage(
    setup: _Setup, invalid: str
) -> None:
    service, repo, master, actor, _ = setup
    target = reference().model_dump(mode="json")
    if invalid == "draft":
        target["approval"] = None
    elif invalid == "foreign":
        target["tenant_id"] = "other-tenant"
    elif invalid == "identity":
        target["identity"]["store_id"] = "other-store"
    elif invalid == "stale":
        master.find_approved.return_value = reference(2)
    master.get_version.return_value = type(reference()).model_validate(target)
    with pytest.raises(AgreementMasterError):
        await service.create_case(actor=actor, package=associated_package())
    repo.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_ap_reassessment_does_not_restamp_confirmation(setup: _Setup) -> None:
    service, repo, master, actor, case = setup
    master.get_version.return_value = reference()
    await service.create_case(actor=actor, package=associated_package())
    saved = repo.create.await_args.kwargs
    stored = case.model_copy(
        update={"package": saved["package"], "assessment": saved["assessment"]}
    )
    repo.get_version.return_value = stored
    before = stored.package.association.model_dump(mode="json")
    await service.decide_case(
        actor=actor,
        case_id=case.case_id,
        expected_version=1,
        decision=APDecision(action="approve", reason="Reviewed case"),
    )
    assert stored.package.association.model_dump(mode="json") == before
    repo.decide.assert_awaited_once()


@pytest.mark.asyncio
async def test_changed_source_cannot_reuse_a_confirmation_as_evidence(setup: _Setup) -> None:
    service, repo, master, actor, _ = setup
    master.get_version.return_value = reference()
    await service.create_case(actor=actor, package=associated_package())
    saved = repo.create.await_args.kwargs["package"].model_dump(mode="json")
    saved["invoice"]["fields"]["invoice_number"] = "CHANGED"
    assessment = ReconciliationEngine(ReconciliationSettings()).assess(
        InvoicePackage.model_validate(saved),
        agreement_start=reference(),
        agreement_end=reference(),
        tenant_id=actor.tenant_id,
    )
    assert any(f.code == "contract_association_invalid" for f in assessment.findings)


@pytest.mark.asyncio
async def test_legacy_packages_keep_source_identifier_requirements(setup: _Setup) -> None:
    service, repo, _, actor, _ = setup
    payload = package().model_dump(mode="json")
    payload["invoice"]["fields"]["vendor_id"] = None
    await service.create_case(actor=actor, package=InvoicePackage.model_validate(payload))
    assert any(
        f.code == "missing_field" for f in repo.create.await_args.kwargs["assessment"].findings
    )
