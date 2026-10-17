"""AP decisions pin case content, policy, and approved agreement authority."""

from datetime import date, datetime, timezone
from typing import Any
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from src.paper.contracts import (
    AgreementActor,
    AgreementDraft,
    AgreementIdentity,
    AgreementVersion,
    ApprovalRecord,
)
from src.paper.errors import AgreementMasterError
from src.paper.reconciliation.contracts import (
    APDecision,
    InvoiceCaseVersion,
    InvoicePackage,
    ReconciliationFinding,
    RentInvoiceDocument,
    TaxInvoiceDocument,
)
from src.paper.reconciliation.engine import ReconciliationEngine
from src.paper.reconciliation.ports.case_repository import BaseInvoiceCaseRepository
from src.paper.reconciliation.ports.rule import BaseReconciliationRule
from src.paper.reconciliation.settings import ReconciliationSettings
from src.paper.reconciliation.workflow import InvoiceCaseService
from src.paper.schemas import RentAgreementSchema, RentInvoiceSchema, TaxInvoiceSchema
from src.paper.service import AgreementMasterService

_Setup = tuple[InvoiceCaseService, AsyncMock, AsyncMock, AgreementActor, InvoiceCaseVersion]


def package() -> InvoicePackage:
    identity = AgreementIdentity(vendor_id="vendor-1", store_id="store-1", contract_number="RA-1")
    return InvoicePackage(
        identity=identity,
        invoice=RentInvoiceDocument(
            source_document_id="invoice-source",
            fields=RentInvoiceSchema(
                **identity.model_dump(),
                invoice_number="INV-1",
                invoice_date=date(2026, 6, 1),
                service_period_start=date(2026, 6, 1),
                service_period_end=date(2026, 6, 30),
                currency="IDR",
                subtotal="100.00",
                tax_amount="10.00",
                total="110.00",
                bank_account="001234",
            ),
        ),
        tax_invoices=(
            TaxInvoiceDocument(
                source_document_id="tax-source",
                fields=TaxInvoiceSchema(
                    **identity.model_dump(),
                    invoice_number="INV-1",
                    tax_invoice_number="TAX-1",
                    tax_invoice_date=date(2026, 6, 1),
                    currency="IDR",
                    taxable_amount="100.00",
                    tax_amount="10.00",
                    total="110.00",
                ),
            ),
        ),
    )


def reference(version_number: int = 1) -> AgreementVersion:
    now = datetime.now(timezone.utc)
    return AgreementVersion(
        agreement_id="agreement-1",
        tenant_id="tenant-1",
        version_number=version_number,
        identity=package().identity,
        draft=AgreementDraft(
            terms=RentAgreementSchema(
                **package().identity.model_dump(),
                vendor_name="Landlord",
                lease_start_date=date(2026, 1, 1),
                lease_end_date=date(2026, 12, 31),
                payment_schedule="Monthly",
                rent_type="fixed",
                currency="IDR",
                fixed_rent="100.00",
                bank_account="001234",
                extensions={"fixed_rent_basis": "per_invoice"},
            ),
            effective_from=date(2026, 1, 1),
            effective_to=date(2026, 12, 31),
            source_document_ids=("agreement-source",),
            change_reason="Reviewed source",
        ),
        created_by="author",
        created_at=now,
        approval=ApprovalRecord(
            classification="non_psak73",
            rule_set_id="accounting-policy",
            rule_set_version="1",
            reason="Reviewed",
            approved_by="reviewer",
            approved_at=now,
        ),
    )


@pytest.fixture
def setup() -> _Setup:
    actor = AgreementActor(tenant_id="tenant-1", user_id="reviewer", can_approve=True)
    settings = ReconciliationSettings()
    engine = ReconciliationEngine(settings)
    assessment = engine.assess(
        package(), agreement_start=reference(), agreement_end=reference(), tenant_id="tenant-1"
    )
    case = InvoiceCaseVersion(
        case_id="case-1",
        tenant_id="tenant-1",
        version_number=1,
        package=package(),
        assessment=assessment,
        created_by="author",
        created_at=datetime.now(timezone.utc),
    )
    repository = AsyncMock(spec=BaseInvoiceCaseRepository)
    repository.get_version.return_value = case
    repository.create.return_value = case
    repository.append.return_value = case
    repository.decide.return_value = case
    repository.list_versions.return_value = (case,)
    repository.list_latest.return_value = (case,)
    master = AsyncMock(spec=AgreementMasterService)
    master.find_approved.return_value = reference()
    service = InvoiceCaseService(repository, master=master, engine=engine, settings=settings)
    return service, repository, master, actor, case


@pytest.mark.asyncio
async def test_create_pins_both_period_endpoints_and_persists_assessment(setup: _Setup) -> None:
    service, repository, master, actor, _ = setup
    await service.create_case(actor=actor, package=package())
    assert master.find_approved.await_count == 2
    assert [call.kwargs["lookup"].as_of for call in master.find_approved.await_args_list] == [
        date(2026, 6, 1),
        date(2026, 6, 30),
    ]
    saved = repository.create.await_args.kwargs
    assert saved["actor"].tenant_id == "tenant-1"
    assert saved["assessment"].outcome == "matched"
    assert len(saved["duplicate_key"]) == 64


@pytest.mark.asyncio
async def test_missing_period_is_persisted_incomplete_without_lookup(setup: _Setup) -> None:
    service, repository, master, actor, _ = setup
    body = package().model_dump(mode="json")
    body["invoice"]["fields"]["service_period_start"] = None
    await service.create_case(actor=actor, package=InvoicePackage.model_validate(body))
    master.find_approved.assert_not_awaited()
    assert repository.create.await_args.kwargs["assessment"].outcome == "incomplete"


@pytest.mark.asyncio
async def test_explicit_installment_allocation_looks_up_authority_without_filling_source_dates(
    setup: _Setup,
) -> None:
    from src.paper.reconciliation.composition import build_reconciliation_engine

    _, repository, master, actor, _ = setup
    settings = ReconciliationSettings(enabled_rules=("installments", "withholding"))
    body = package().model_dump(mode="json")
    body["invoice"]["fields"].update(
        service_period_start=None, service_period_end=None, installment_id="stage-1"
    )
    body["review_context"] = {
        "allocation_start": "2026-06-01",
        "allocation_end": "2026-06-30",
        "reason": "Reviewer allocated advance payment using approved schedule, not invoice evidence",
        "source_document_ids": ["agreement-source"],
    }
    incoming = InvoicePackage.model_validate(body)
    service = InvoiceCaseService(
        repository, master=master, engine=build_reconciliation_engine(settings), settings=settings
    )
    await service.create_case(actor=actor, package=incoming)
    assert [call.kwargs["lookup"].as_of for call in master.find_approved.await_args_list] == [
        date(2026, 6, 1),
        date(2026, 6, 30),
    ]
    retained = repository.create.await_args.kwargs["package"]
    assert retained.invoice.fields.service_period_start is None
    assert retained.invoice.fields.service_period_end is None
    assert retained.review_context == incoming.review_context
    # A free-form allocation alone cannot substitute for an approved schedule.
    assert repository.create.await_args.kwargs["assessment"].outcome != "matched"


@pytest.mark.asyncio
async def test_disabled_installment_rule_does_not_use_review_allocation_for_authority(
    setup: _Setup,
) -> None:
    service, repository, master, actor, _ = setup
    body = package().model_dump(mode="json")
    body["invoice"]["fields"].update(service_period_start=None, service_period_end=None)
    body["review_context"] = {
        "allocation_start": "2026-06-01",
        "allocation_end": "2026-06-30",
        "reason": "Cannot enable an unconfigured rule using package data",
        "source_document_ids": ["agreement-source"],
    }
    await service.create_case(actor=actor, package=InvoicePackage.model_validate(body))
    master.find_approved.assert_not_awaited()
    assert repository.create.await_args.kwargs["assessment"].outcome == "incomplete"


@pytest.mark.asyncio
async def test_installment_approval_requires_its_retained_atomic_claim(setup: _Setup) -> None:
    service, repository, _, actor, current = setup
    body = current.model_dump(mode="json")
    body["package"]["invoice"]["fields"]["installment_id"] = "stage-1"
    current = InvoiceCaseVersion.model_validate(body)
    repository.get_version.return_value = current
    repository.duplicate_owner.return_value = None
    service._assess = AsyncMock(return_value=current.assessment)  # type: ignore[method-assign]
    with pytest.raises(AgreementMasterError, match="installment"):
        await service.decide_case(
            actor=actor,
            case_id=current.case_id,
            expected_version=1,
            decision=APDecision(action="approve", reason="Claim must exist before approval"),
        )
    repository.decide.assert_not_awaited()


@pytest.mark.asyncio
async def test_revision_cannot_change_canonical_identity(setup: _Setup) -> None:
    service, repository, _, actor, _ = setup
    body = package().model_dump(mode="json")
    body["identity"]["vendor_id"] = "another-vendor"
    with pytest.raises(AgreementMasterError) as error:
        await service.revise_case(
            actor=actor,
            case_id="case-1",
            expected_version=1,
            package=InvoicePackage.model_validate(body),
        )
    assert error.value.code == "invalid_agreement"
    repository.append.assert_not_awaited()


@pytest.mark.asyncio
async def test_approval_locks_before_revalidating_reference(setup: _Setup) -> None:
    service, repository, master, actor, _ = setup
    trace: list[str] = []

    async def locked(**kwargs: Any) -> None:
        trace.append("locked")

    async def looked_up(**kwargs: Any) -> AgreementVersion:
        trace.append("lookup")
        return reference()

    repository.lock_for_decision.side_effect = locked
    master.find_approved.side_effect = looked_up
    await service.decide_case(
        actor=actor,
        case_id="case-1",
        expected_version=1,
        decision=APDecision(action="approve", reason="Reviewed package"),
    )
    assert trace == ["locked", "lookup", "lookup"]
    repository.lock_for_decision.assert_awaited_once_with(
        case_id="case-1", expected_version=1, actor=actor, agreement_id="agreement-1"
    )
    repository.decide.assert_awaited_once()


@pytest.mark.asyncio
async def test_changed_agreement_rejects_stale_approval(setup: _Setup) -> None:
    service, repository, master, actor, _ = setup
    master.find_approved.return_value = reference(2)
    with pytest.raises(AgreementMasterError) as error:
        await service.decide_case(
            actor=actor,
            case_id="case-1",
            expected_version=1,
            decision=APDecision(action="approve", reason="Reviewed package"),
        )
    assert error.value.code == "conflict"
    repository.decide.assert_not_awaited()


@pytest.mark.asyncio
async def test_changed_policy_rejects_stale_approval(setup: _Setup) -> None:
    _, repository, master, actor, _ = setup
    settings = ReconciliationSettings(policy_version="2")
    service = InvoiceCaseService(
        repository, master=master, engine=ReconciliationEngine(settings), settings=settings
    )
    with pytest.raises(AgreementMasterError) as error:
        await service.decide_case(
            actor=actor,
            case_id="case-1",
            expected_version=1,
            decision=APDecision(action="approve", reason="Reviewed package"),
        )
    assert error.value.code == "conflict"
    repository.decide.assert_not_awaited()


@pytest.mark.asyncio
async def test_duplicate_case_cannot_be_approved_even_with_override(setup: _Setup) -> None:
    service, repository, _, actor, case = setup
    repository.get_version.return_value = case.model_copy(update={"duplicate_of": "earlier-case"})
    with pytest.raises(AgreementMasterError) as error:
        await service.decide_case(
            actor=actor,
            case_id="case-1",
            expected_version=1,
            decision=APDecision(action="approve", reason="Reviewed package"),
        )
    assert error.value.code == "invalid_approval"
    repository.decide.assert_not_awaited()


@pytest.mark.asyncio
async def test_incomplete_package_cannot_be_overridden(setup: _Setup) -> None:
    service, repository, _, actor, case = setup
    body = package().model_dump(mode="json")
    body["tax_invoices"] = []
    missing = InvoicePackage.model_validate(body)
    assessment = ReconciliationEngine(ReconciliationSettings()).assess(
        missing, agreement_start=reference(), agreement_end=reference(), tenant_id="tenant-1"
    )
    repository.get_version.return_value = case.model_copy(
        update={"package": missing, "assessment": assessment}
    )
    with pytest.raises(AgreementMasterError) as error:
        await service.decide_case(
            actor=actor,
            case_id="case-1",
            expected_version=1,
            decision=APDecision(action="approve", reason="Reviewed package"),
        )
    assert error.value.code == "invalid_approval"
    repository.decide.assert_not_awaited()


@pytest.mark.asyncio
async def test_explicit_allowed_override_is_recorded(setup: _Setup) -> None:
    service, repository, _, actor, case = setup
    body = package().model_dump(mode="json")
    body["invoice"]["fields"]["bank_account"] = "009999"
    changed = InvoicePackage.model_validate(body)
    assessment = ReconciliationEngine(ReconciliationSettings()).assess(
        changed, agreement_start=reference(), agreement_end=reference(), tenant_id="tenant-1"
    )
    repository.get_version.return_value = case.model_copy(
        update={"package": changed, "assessment": assessment}
    )
    await service.decide_case(
        actor=actor,
        case_id="case-1",
        expected_version=1,
        decision=APDecision(
            action="approve",
            reason="Confirmed beneficiary independently",
            override_codes=("bank_mismatch",),
        ),
    )
    assert repository.decide.await_args.kwargs["decision"].override_codes == ("bank_mismatch",)


@pytest.mark.asyncio
async def test_unnecessary_override_is_rejected(setup: _Setup) -> None:
    service, repository, _, actor, _ = setup
    with pytest.raises(AgreementMasterError) as error:
        await service.decide_case(
            actor=actor,
            case_id="case-1",
            expected_version=1,
            decision=APDecision(
                action="approve", reason="Reviewed package", override_codes=("bank_mismatch",)
            ),
        )
    assert error.value.code == "invalid_approval"
    repository.decide.assert_not_awaited()


@pytest.mark.asyncio
async def test_rejection_does_not_require_current_master(setup: _Setup) -> None:
    service, repository, master, actor, _ = setup
    await service.decide_case(
        actor=actor,
        case_id="case-1",
        expected_version=1,
        decision=APDecision(action="reject", reason="Vendor correction required"),
    )
    master.find_approved.assert_not_awaited()
    assert repository.lock_for_decision.await_args.kwargs["agreement_id"] is None
    repository.decide.assert_awaited_once()


@pytest.mark.asyncio
async def test_authority_is_required_for_all_ap_decisions(setup: _Setup) -> None:
    service, repository, _, actor, _ = setup
    author = actor.model_copy(update={"can_approve": False})
    with pytest.raises(AgreementMasterError) as error:
        await service.decide_case(
            actor=author,
            case_id="case-1",
            expected_version=1,
            decision=APDecision(action="reject", reason="Reviewed"),
        )
    assert error.value.code == "forbidden"
    repository.lock_for_decision.assert_not_awaited()


@pytest.mark.asyncio
async def test_cross_tenant_read_is_not_found(setup: _Setup) -> None:
    service, repository, _, actor, _ = setup
    repository.get_version.return_value = None
    with pytest.raises(AgreementMasterError) as error:
        await service.get_version(actor=actor, case_id="other-case", version_number=1)
    assert error.value.code == "not_found"


@pytest.mark.asyncio
async def test_history_and_case_lists_are_scoped_and_bounded(setup: _Setup) -> None:
    service, repository, _, actor, _ = setup
    await service.list_cases(actor=actor, limit=10, offset=2)
    repository.list_latest.assert_awaited_once_with(tenant_id="tenant-1", limit=10, offset=2)
    with pytest.raises(ValidationError):
        await service.list_cases(actor=actor, limit=101)


@pytest.mark.asyncio
async def test_storage_timeout_is_sanitized(setup: _Setup) -> None:
    service, repository, _, actor, _ = setup
    repository.get_version.side_effect = TimeoutError("private database address")
    with pytest.raises(AgreementMasterError) as error:
        await service.get_version(actor=actor, case_id="case-1", version_number=1)
    assert error.value.code == "timeout"
    assert "private database" not in str(error.value)


class _ClearHostRule(BaseReconciliationRule):
    @property
    def rule_id(self) -> str:
        return "host-rule"

    @property
    def rule_version(self) -> str:
        return "1"

    def evaluate(
        self,
        package: InvoicePackage,
        *,
        agreement: AgreementVersion | None,
        settings: ReconciliationSettings,
    ) -> tuple[ReconciliationFinding, ...]:
        return ()


@pytest.mark.asyncio
async def test_versioned_host_rule_can_be_embedded_without_policy_rejection(setup: _Setup) -> None:
    _, repository, master, actor, _ = setup
    settings = ReconciliationSettings()
    engine = ReconciliationEngine(settings, extra_rules=(_ClearHostRule(),))
    service = InvoiceCaseService(repository, master=master, engine=engine, settings=settings)
    await service.create_case(actor=actor, package=package())
    assessment = repository.create.await_args.kwargs["assessment"]
    assert assessment.outcome == "matched"
    assert assessment.policy_fingerprint == engine.policy_fingerprint


@pytest.mark.asyncio
async def test_engine_and_workflow_settings_must_agree(setup: _Setup) -> None:
    _, repository, master, actor, _ = setup
    service = InvoiceCaseService(
        repository,
        master=master,
        engine=ReconciliationEngine(ReconciliationSettings()),
        settings=ReconciliationSettings(policy_version="different-policy"),
    )
    with pytest.raises(AgreementMasterError) as error:
        await service.create_case(actor=actor, package=package())
    assert error.value.code == "invalid_configuration"
    repository.create.assert_not_awaited()
