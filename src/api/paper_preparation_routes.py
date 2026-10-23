"""Explicit reviewed-document selection and read-only case readiness."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.paper_case_routes import (
    get_invoice_actor,
    get_invoice_case_service,
    get_reconciliation_settings,
)
from src.api.paper_document_draft_routes import get_document_draft_service
from src.api.paper_routes import _commit, _domain_errors, _rate_limit, get_paper_db
from src.paper.contracts import AgreementActor
from src.paper.preparation.request import PrepareCaseRequest
from src.paper.preparation.service import CasePreparationService
from src.paper.readiness import ReadinessResult
from src.paper.reconciliation.contracts import InvoiceCaseVersion
from src.paper.reconciliation.settings import ReconciliationSettings
from src.paper.reconciliation.workflow import InvoiceCaseService
from src.services.paper_document_drafts import DocumentDraftService

router = APIRouter(
    prefix="/v1/paper/cases",
    tags=["paper-case-preparation"],
    dependencies=[Depends(_rate_limit)],
)


async def get_case_preparation_service(
    drafts: Annotated[DocumentDraftService, Depends(get_document_draft_service)],
    cases: Annotated[InvoiceCaseService, Depends(get_invoice_case_service)],
    settings: Annotated[ReconciliationSettings, Depends(get_reconciliation_settings)],
) -> CasePreparationService:
    """Inject shared-transaction storage and host-owned requirements."""
    return CasePreparationService(drafts, cases, settings)


@router.post("/preparation/readiness", response_model=ReadinessResult)
async def check_case_readiness(
    body: PrepareCaseRequest,
    actor: Annotated[AgreementActor, Depends(get_invoice_actor)],
    service: Annotated[CasePreparationService, Depends(get_case_preparation_service)],
) -> ReadinessResult:
    """Read selected reviewed versions and current authority without saving a case."""
    with _domain_errors():
        return await service.check(actor=actor, request=body)


@router.post("/from-drafts", response_model=InvoiceCaseVersion, status_code=201)
async def reconcile_selected_documents(
    body: PrepareCaseRequest,
    actor: Annotated[AgreementActor, Depends(get_invoice_actor)],
    service: Annotated[CasePreparationService, Depends(get_case_preparation_service)],
    db: Annotated[AsyncSession, Depends(get_paper_db)],
) -> InvoiceCaseVersion:
    """Recheck readiness and persist a new assessment from exact reviewed versions."""
    with _domain_errors():
        result = await service.reconcile(actor=actor, request=body)
        await _commit(db)
        return result
