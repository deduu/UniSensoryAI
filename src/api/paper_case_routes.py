"""Authenticated durable PAPER invoice cases and explicit AP decisions."""

import asyncio
import os
from pathlib import Path as FilePath
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Request
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth import UserContext, get_user_context
from src.api.paper_review_context import PaperReviewContext
from src.api.paper_routes import (
    _commit,
    _domain_errors,
    _rate_limit,
    get_agreement_actor,
    get_agreement_service,
    get_paper_db,
    get_paper_settings,
)
from src.db.models.user import User
from src.paper.association.candidates import AssociationCandidates
from src.paper.association.query import AssociationQuery
from src.paper.association.service import AssociationService
from src.paper.association.settings import AssociationSettings, load_association_settings
from src.paper.contracts import AgreementActor
from src.paper.errors import AgreementMasterError
from src.paper.field_policy.service import FieldPolicyService
from src.paper.reconciliation.composition import (
    build_reconciliation_engine,
    load_reconciliation_settings,
)
from src.paper.reconciliation.contracts import (
    APDecision,
    InvoiceCaseVersion,
    InvoicePackage,
    ReviseInvoiceCaseRequest,
)
from src.paper.reconciliation.settings import ReconciliationSettings
from src.paper.reconciliation.workflow import InvoiceCaseService
from src.paper.service import AgreementMasterService
from src.paper.settings import AgreementMasterSettings
from src.services.invoice_case_repository import SqlAlchemyInvoiceCaseRepository
from src.services.paper_field_policy_repository import SqlAlchemyFieldPolicyRepository

router = APIRouter(
    prefix="/v1/paper/cases",
    tags=["paper-cases"],
    dependencies=[Depends(_rate_limit)],
)
review_router = APIRouter(
    prefix="/v1/paper",
    tags=["paper"],
    dependencies=[Depends(_rate_limit)],
)


def _settings(value: object) -> ReconciliationSettings:
    try:
        if isinstance(value, ReconciliationSettings):
            value = value.model_dump(mode="json")
        return ReconciliationSettings.model_validate(value)
    except ValidationError:
        raise AgreementMasterError(
            "invalid_configuration", "Reconciliation policy is invalid."
        ) from None


async def get_base_reconciliation_settings(request: Request) -> ReconciliationSettings:
    """Load and cache server-owned reconciliation policy per application.

    Args:
        request: Current application whose state owns its cache and first-load lock.

    Returns:
        A validated independent copy of the configured policy.
    """
    with _domain_errors():
        current = getattr(request.app.state, "paper_reconciliation_settings", None)
        if current is not None:
            return _settings(current)
        lock = getattr(request.app.state, "paper_reconciliation_settings_lock", None)
        if lock is None:
            lock = asyncio.Lock()
            request.app.state.paper_reconciliation_settings_lock = lock
        async with lock:
            current = getattr(request.app.state, "paper_reconciliation_settings", None)
            if current is None:
                configured = os.getenv("PAPER_RECONCILIATION_CONFIG_PATH")
                current = await load_reconciliation_settings(
                    FilePath(configured) if configured else None
                )
                request.app.state.paper_reconciliation_settings = current
            return _settings(current)


async def get_reconciliation_settings(
    user: Annotated[UserContext, Depends(get_user_context)],
    db: Annotated[AsyncSession, Depends(get_paper_db)],
    base: Annotated[ReconciliationSettings, Depends(get_base_reconciliation_settings)],
) -> ReconciliationSettings:
    """Resolve durable tenant overrides for every matching and decision request."""
    with _domain_errors():
        return await FieldPolicyService(SqlAlchemyFieldPolicyRepository(db), base).effective(
            tenant_id=user.tenant_id
        )


async def get_invoice_actor(
    user: Annotated[UserContext, Depends(get_user_context)],
    db: Annotated[AsyncSession, Depends(get_paper_db)],
    settings: Annotated[ReconciliationSettings, Depends(get_base_reconciliation_settings)],
) -> AgreementActor:
    """Resolve AP authority using persisted user roles in the current tenant.

    Args:
        user: Identity supplied by existing authentication.
        db: Write-capable host session shared with case and agreement operations.
        settings: Server-owned AP role allowlist and storage deadline.

    Returns:
        Trusted actor; synthetic identities cannot decide without a persisted role.
    """
    with _domain_errors():
        try:
            result = await asyncio.wait_for(
                db.execute(
                    select(User).where(User.id == user.user_id, User.tenant_id == user.tenant_id)
                ),
                timeout=settings.repository_timeout_seconds,
            )
        except asyncio.TimeoutError:
            raise AgreementMasterError(
                "timeout", "AP authorization exceeded its deadline."
            ) from None
        stored = result.scalar_one_or_none()
        allowed = (
            stored is not None
            and stored.tenant_id == user.tenant_id
            and stored.role in settings.approver_roles
        )
    return AgreementActor(tenant_id=user.tenant_id, user_id=user.user_id, can_approve=allowed)


async def get_contract_association_service(
    request: Request,
    master: Annotated[AgreementMasterService, Depends(get_agreement_service)],
) -> AssociationService:
    """Compose model-independent suggestions with host-owned policy and scoped storage.

    Args:
        request: Application configuration cache; clients cannot select policy.
        master: Injected agreement service in the request transaction.

    Returns:
        Read-only candidate discovery and exact association validation.
    """
    with _domain_errors():
        lock = getattr(request.app.state, "paper_association_lock", None)
        if lock is None:
            lock = asyncio.Lock()
            request.app.state.paper_association_lock = lock
        async with lock:
            settings = getattr(request.app.state, "paper_association_settings", None)
            if settings is None:
                configured = os.getenv("PAPER_ASSOCIATION_CONFIG_PATH")
                settings = await load_association_settings(
                    FilePath(configured) if configured else None
                )
                request.app.state.paper_association_settings = settings
            return AssociationService(master, settings=AssociationSettings.model_validate(settings))


async def get_invoice_case_service(
    db: Annotated[AsyncSession, Depends(get_paper_db)],
    master: Annotated[AgreementMasterService, Depends(get_agreement_service)],
    settings: Annotated[ReconciliationSettings, Depends(get_reconciliation_settings)],
    association: Annotated[AssociationService, Depends(get_contract_association_service)],
) -> InvoiceCaseService:
    """Compose case storage and approved agreement reads in one transaction.

    Args:
        db: Host session shared by both repository adapters.
        master: Existing approved agreement service using the same session.
        settings: Host-owned completeness, matching, and AP policy.
        association: Injected candidate and confirmation validation policy.

    Returns:
        Model-independent case workflow with injected deterministic rules.
    """
    return InvoiceCaseService(
        SqlAlchemyInvoiceCaseRepository(db),
        master=master,
        engine=build_reconciliation_engine(settings),
        settings=settings,
        association=association,
    )


@review_router.get("/review-context", response_model=PaperReviewContext)
async def read_paper_review_context(
    agreement_actor: Annotated[AgreementActor, Depends(get_agreement_actor)],
    case_actor: Annotated[AgreementActor, Depends(get_invoice_actor)],
    agreement_settings: Annotated[AgreementMasterSettings, Depends(get_paper_settings)],
    case_settings: Annotated[ReconciliationSettings, Depends(get_reconciliation_settings)],
) -> PaperReviewContext:
    """Expose current host policy and trusted reviewer permissions for UI guidance.

    Args:
        agreement_actor: Agreement reviewer resolved from persisted tenant roles.
        case_actor: AP reviewer resolved against the separate case role policy.
        agreement_settings: Server-owned agreement publication requirements.
        case_settings: Server-owned completeness and permissible exception policy.

    Returns:
        Validated read-only guidance, without configuration paths or role lists.
    """
    return PaperReviewContext(
        user_id=agreement_actor.user_id,
        can_approve_agreements=agreement_actor.can_approve,
        can_decide_cases=case_actor.can_approve,
        agreement_required_fields=agreement_settings.required_agreement_fields,
        agreement_required_fields_by_rent_type=agreement_settings.required_fields_by_rent_type,
        required_invoice_fields=case_settings.required_invoice_fields,
        required_tax_fields=case_settings.required_tax_fields,
        required_documents=case_settings.required_documents,
        required_supporting_types=case_settings.required_supporting_types,
        override_codes=case_settings.override_codes,
        policy_id=case_settings.policy_id,
        policy_version=case_settings.policy_version,
        field_requirements=case_settings.field_requirements,
        enabled_rules=case_settings.enabled_rules,
        allow_withholding_without_vat_invoice=case_settings.allow_withholding_without_vat_invoice,
        withholding_required_supporting_types=case_settings.withholding_required_supporting_types,
        require_independent_agreement_approval=agreement_settings.require_independent_approval,
        require_independent_case_approval=case_settings.require_independent_approval,
    )


@router.post("/association/candidates", response_model=AssociationCandidates)
async def suggest_contract_associations(
    body: AssociationQuery,
    actor: Annotated[AgreementActor, Depends(get_invoice_actor)],
    service: Annotated[AssociationService, Depends(get_contract_association_service)],
) -> AssociationCandidates:
    """Suggest approved contracts without assigning identity or changing stored data.

    Args:
        body: Source invoice and optional reviewed coverage, with bounded catalog paging.
        actor: Trusted tenant scope established by the host.
        service: Injected deterministic discovery service.

    Returns:
        Ranked candidates, match explanations, coverage and scan continuation.
    """
    with _domain_errors():
        return await service.suggest(actor=actor, query=body)


@router.post("", response_model=InvoiceCaseVersion, status_code=201)
async def create_invoice_case(
    body: InvoicePackage,
    actor: Annotated[AgreementActor, Depends(get_invoice_actor)],
    service: Annotated[InvoiceCaseService, Depends(get_invoice_case_service)],
    db: Annotated[AsyncSession, Depends(get_paper_db)],
) -> InvoiceCaseVersion:
    """Assess typed source fields and commit a durable initial invoice case.

    Args:
        body: Package of source-derived fields and document roles.
        actor: Server-established author and tenant.
        service: Injected case workflow.
        db: Host transaction to commit before returning success.

    Returns:
        Initial case version, including findings or a duplicate disposition.
    """
    with _domain_errors():
        # Manual imports own their fields. Only from-drafts resolves immutable review provenance.
        manual = body.model_copy(update={"document_draft_references": ()})
        result = await service.create_case(actor=actor, package=manual)
        await _commit(db)
        return result


@router.get("", response_model=tuple[InvoiceCaseVersion, ...])
async def list_invoice_cases(
    actor: Annotated[AgreementActor, Depends(get_invoice_actor)],
    service: Annotated[InvoiceCaseService, Depends(get_invoice_case_service)],
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> tuple[InvoiceCaseVersion, ...]:
    """Read one latest version per case in the current tenant.

    Args:
        actor: Server-established tenant identity.
        service: Injected case workflow.
        limit: Page size between one and 100.
        offset: Nonnegative number of cases to skip.

    Returns:
        Current case versions, newest created case first.
    """
    with _domain_errors():
        return await service.list_cases(actor=actor, limit=limit, offset=offset)


@router.post("/{case_id}/versions", response_model=InvoiceCaseVersion, status_code=201)
async def revise_invoice_case(
    case_id: Annotated[str, Path(min_length=1, max_length=128, pattern=r"\S")],
    body: ReviseInvoiceCaseRequest,
    actor: Annotated[AgreementActor, Depends(get_invoice_actor)],
    service: Annotated[InvoiceCaseService, Depends(get_invoice_case_service)],
    db: Annotated[AsyncSession, Depends(get_paper_db)],
) -> InvoiceCaseVersion:
    """Append corrected documents and findings with a latest-version guard.

    Args:
        case_id: Existing case identifier.
        body: Expected revision and corrected source package.
        actor: Server-established tenant and author.
        service: Injected case workflow.
        db: Host transaction to commit before returning success.

    Returns:
        New undecided version retaining previous history and AP records.
    """
    with _domain_errors():
        result = await service.revise_case(
            actor=actor,
            case_id=case_id,
            expected_version=body.expected_version,
            package=body.package.model_copy(update={"document_draft_references": ()}),
        )
        await _commit(db)
        return result


@router.get("/{case_id}/versions", response_model=tuple[InvoiceCaseVersion, ...])
async def list_invoice_case_versions(
    case_id: Annotated[str, Path(min_length=1, max_length=128, pattern=r"\S")],
    actor: Annotated[AgreementActor, Depends(get_invoice_actor)],
    service: Annotated[InvoiceCaseService, Depends(get_invoice_case_service)],
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> tuple[InvoiceCaseVersion, ...]:
    """Read stored case history within the current tenant.

    Args:
        case_id: Case identifier to read.
        actor: Server-established tenant identity.
        service: Injected case workflow.
        limit: Page size between one and 100.
        offset: Nonnegative number of revisions to skip.

    Returns:
        Historical versions, newest first.
    """
    with _domain_errors():
        return await service.list_versions(actor=actor, case_id=case_id, limit=limit, offset=offset)


@router.get("/{case_id}/versions/{version_number}", response_model=InvoiceCaseVersion)
async def read_invoice_case_version(
    case_id: Annotated[str, Path(min_length=1, max_length=128, pattern=r"\S")],
    version_number: Annotated[int, Path(ge=1)],
    actor: Annotated[AgreementActor, Depends(get_invoice_actor)],
    service: Annotated[InvoiceCaseService, Depends(get_invoice_case_service)],
) -> InvoiceCaseVersion:
    """Read an exact historical case revision within the current tenant.

    Args:
        case_id: Case identifier to read.
        version_number: Exact historical version.
        actor: Server-established tenant identity.
        service: Injected case workflow.

    Returns:
        Stored package, findings, duplicate disposition, and any AP record.
    """
    with _domain_errors():
        return await service.get_version(
            actor=actor, case_id=case_id, version_number=version_number
        )


@router.post("/{case_id}/versions/{version_number}/decision", response_model=InvoiceCaseVersion)
async def decide_invoice_case(
    case_id: Annotated[str, Path(min_length=1, max_length=128, pattern=r"\S")],
    version_number: Annotated[int, Path(ge=1)],
    body: APDecision,
    actor: Annotated[AgreementActor, Depends(get_invoice_actor)],
    service: Annotated[InvoiceCaseService, Depends(get_invoice_case_service)],
    db: Annotated[AsyncSession, Depends(get_paper_db)],
) -> InvoiceCaseVersion:
    """Commit an authorized AP disposition after case/reference revalidation.

    Args:
        case_id: Case identifier to decide.
        version_number: Exact latest revision reviewed by AP.
        body: Explicit action, reason, and configured finding overrides.
        actor: Server-resolved AP authority and tenant.
        service: Injected case workflow.
        db: Shared case/agreement transaction to commit before success.

    Returns:
        Stored version with immutable AP reviewer identity and UTC decision time.
    """
    with _domain_errors():
        result = await service.decide_case(
            actor=actor,
            case_id=case_id,
            expected_version=version_number,
            decision=body,
        )
        await _commit(db)
        return result
