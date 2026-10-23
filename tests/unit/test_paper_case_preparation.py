"""Case preparation binds reviewed snapshots without writing assessment history."""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError
from test_paper_case_workflow import package, reference

from src.paper.association.selection import AssociationSelection
from src.paper.association.service import AssociationService
from src.paper.contracts import AgreementActor
from src.paper.errors import AgreementMasterError
from src.paper.preparation.request import PrepareCaseRequest
from src.paper.preparation.service import CasePreparationService
from src.paper.reconciliation.contracts import InvoiceCaseVersion
from src.paper.reconciliation.engine import ReconciliationEngine
from src.paper.reconciliation.ports.case_repository import BaseInvoiceCaseRepository
from src.paper.reconciliation.settings import ReconciliationSettings
from src.paper.reconciliation.workflow import InvoiceCaseService
from src.paper.service import AgreementMasterService


def draft(status: str = "reviewed", tenant: str = "tenant-1") -> SimpleNamespace:
    return SimpleNamespace(
        draft_id="draft-1",
        tenant_id=tenant,
        version_number=2,
        role="rent_invoice",
        document=package().invoice,
        status=status,
        reviewed_by="reviewer" if status == "reviewed" else None,
        reviewed_at=datetime.now(timezone.utc) if status == "reviewed" else None,
    )


def request() -> PrepareCaseRequest:
    return PrepareCaseRequest(
        identity=package().identity,
        invoice={"draft_id": "draft-1", "version_number": 2},
    )


@pytest.mark.asyncio
async def test_prepare_resolves_exact_reviewed_version_and_retains_source() -> None:
    drafts = AsyncMock()
    drafts.get_version.return_value = draft()
    service = CasePreparationService(drafts, AsyncMock(), ReconciliationSettings())
    actor = AgreementActor(tenant_id="tenant-1", user_id="author", can_approve=False)
    result = await service.resolve(actor=actor, request=request())
    assert result.invoice == package().invoice
    assert result.document_draft_references[0].version_number == 2
    assert result.document_draft_references[0].reviewed_by == "reviewer"
    assert drafts.get_version.await_args.kwargs["version_number"] == 2
    assert drafts.get_version.await_args.kwargs["actor"] == actor


@pytest.mark.asyncio
@pytest.mark.parametrize("record", [draft("draft"), draft(tenant="other")])
async def test_unreviewed_or_cross_tenant_source_cannot_enter_case(record: object) -> None:
    drafts = AsyncMock()
    drafts.get_version.return_value = record
    service = CasePreparationService(drafts, AsyncMock(), ReconciliationSettings())
    with pytest.raises(AgreementMasterError):
        await service.resolve(
            actor=AgreementActor(tenant_id="tenant-1", user_id="author"), request=request()
        )


def test_reference_request_rejects_unpaired_revision_and_duplicate_versions() -> None:
    data = request().model_dump()
    with pytest.raises(ValidationError):
        PrepareCaseRequest.model_validate({**data, "case_id": "case-a"})
    with pytest.raises(ValidationError):
        PrepareCaseRequest.model_validate({**data, "tax_invoices": [data["invoice"]]})


@pytest.mark.asyncio
async def test_preview_is_read_only_and_blocks_run_when_not_ready() -> None:
    drafts, cases = AsyncMock(), AsyncMock()
    drafts.get_version.return_value = draft()
    cases.preview_assessment.return_value = (
        package(),
        SimpleNamespace(),
    )
    service = CasePreparationService(drafts, cases, ReconciliationSettings())
    service.check = AsyncMock(return_value=SimpleNamespace(ready=False))
    with pytest.raises(AgreementMasterError, match="readiness"):
        await service.reconcile(
            actor=AgreementActor(tenant_id="tenant-1", user_id="author"), request=request()
        )
    cases.create_case.assert_not_awaited()
    cases.revise_case.assert_not_awaited()


@pytest.mark.asyncio
async def test_duplicate_source_under_different_draft_ids_is_a_safe_validation_error() -> None:
    from src.paper.reconciliation.contracts import TaxInvoiceDocument

    tax = SimpleNamespace(**vars(draft()))
    tax.draft_id = "tax-draft"
    tax.role = "tax_invoice"
    tax.document = TaxInvoiceDocument(
        **{
            **package().tax_invoices[0].model_dump(),
            "source_document_id": draft().document.source_document_id,
        }
    )
    drafts = AsyncMock()
    drafts.get_version.side_effect = [draft(), tax]
    service = CasePreparationService(drafts, AsyncMock(), ReconciliationSettings())
    body = PrepareCaseRequest.model_validate(
        {
            **request().model_dump(),
            "tax_invoices": [{"draft_id": "tax-draft", "version_number": 2}],
        }
    )
    with pytest.raises(AgreementMasterError, match="distinct source"):
        await service.resolve(
            actor=AgreementActor(tenant_id="tenant-1", user_id="author"), request=body
        )


@pytest.mark.asyncio
async def test_ready_selection_runs_real_engine_and_persists_exact_provenance() -> None:
    source = package()
    invoice, tax = draft(), SimpleNamespace(**vars(draft()))
    tax.draft_id, tax.role, tax.document = "tax-draft", "tax_invoice", source.tax_invoices[0]
    drafts = AsyncMock()
    drafts.get_version.side_effect = lambda **kwargs: (
        invoice if kwargs["draft_id"] == "draft-1" else tax
    )
    repository = AsyncMock(spec=BaseInvoiceCaseRepository)

    async def persist(**kwargs: object) -> InvoiceCaseVersion:
        return InvoiceCaseVersion(
            case_id="case-new",
            tenant_id="tenant-1",
            version_number=1,
            package=kwargs["package"],
            assessment=kwargs["assessment"],
            created_by="reviewer",
            created_at=datetime.now(timezone.utc),
        )

    repository.create.side_effect = persist
    master = AsyncMock(spec=AgreementMasterService)
    master.get_version.return_value = reference()
    master.find_approved.return_value = reference()
    settings = ReconciliationSettings()
    cases = InvoiceCaseService(
        repository,
        master=master,
        engine=ReconciliationEngine(settings),
        settings=settings,
        association=AssociationService(master),
    )
    service = CasePreparationService(drafts, cases, settings)
    body = PrepareCaseRequest(
        identity=source.identity,
        invoice={"draft_id": "draft-1", "version_number": 2},
        tax_invoices=({"draft_id": "tax-draft", "version_number": 2},),
        association=AssociationSelection(
            agreement_id="agreement-1", version_number=1, reason="Reviewed original sources"
        ),
    )
    actor = AgreementActor(tenant_id="tenant-1", user_id="reviewer")
    ready = await service.check(actor=actor, request=body)
    assert ready.ready
    repository.create.assert_not_awaited()
    result = await service.reconcile(actor=actor, request=body)
    assert result.assessment.outcome == "matched"
    assert result.package.invoice == source.invoice
    assert [item.draft_id for item in result.package.document_draft_references] == [
        "draft-1",
        "tax-draft",
    ]
    assert result.package.association.confirmed_by == actor.user_id
    repository.create.assert_awaited_once()
