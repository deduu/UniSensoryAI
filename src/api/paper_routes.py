"""Additive PAPER schema and agreement master HTTP adapter."""

import asyncio
import os
from collections.abc import AsyncIterator, Iterator
from contextlib import contextmanager
from datetime import date
from pathlib import Path as FilePath
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth import UserContext, get_user_context
from src.api.rate_limit import InProcessRateLimiter, RateLimitDep
from src.db.models.user import User
from src.db.session import get_db
from src.extraction.contracts import ExternalSchema
from src.paper.composition import load_agreement_settings
from src.paper.contracts import (
    AgreementActor,
    AgreementIdentity,
    AgreementLookup,
    AgreementVersion,
    ApprovalDecision,
    CreateAgreementRequest,
    ReviseAgreementRequest,
)
from src.paper.errors import AgreementMasterError
from src.paper.schemas import PAPER_SCHEMA_NAMES, get_paper_schema
from src.paper.service import AgreementMasterService
from src.paper.settings import AgreementMasterSettings
from src.services.agreement_repository import SqlAlchemyAgreementRepository

_limiter = InProcessRateLimiter(requests_per_minute=6000, burst=100)
_rate_limit = RateLimitDep(requests_per_minute=6000, limiter=_limiter)
router = APIRouter(prefix="/v1/paper", tags=["paper"], dependencies=[Depends(_rate_limit)])


@contextmanager
def _domain_errors() -> Iterator[None]:
    try:
        yield
    except AgreementMasterError as error:
        statuses = {
            "forbidden": 403,
            "not_found": 404,
            "conflict": 409,
            "invalid_agreement": 422,
            "invalid_approval": 422,
            "timeout": 504,
            "invalid_configuration": 503,
        }
        status = statuses.get(error.code, 500)
        raise HTTPException(
            status_code=status, detail={"code": error.code, "message": str(error)}
        ) from None
    except SQLAlchemyError:
        raise HTTPException(
            status_code=503,
            detail={"code": "storage_unavailable", "message": "Agreement storage is unavailable."},
        ) from None


async def get_paper_db() -> AsyncIterator[AsyncSession]:
    """Yield a write-capable host session with no client-selected replica setting."""
    async for session in get_db():
        yield session


async def get_paper_settings(request: Request) -> AgreementMasterSettings:
    """Cache validated deployment policy per application, without model loading."""
    current = getattr(request.app.state, "paper_settings", None)
    if current is not None:
        return AgreementMasterSettings.model_validate(current)
    lock = getattr(request.app.state, "paper_settings_lock", None)
    if lock is None:
        lock = asyncio.Lock()
        request.app.state.paper_settings_lock = lock
    async with lock:
        current = getattr(request.app.state, "paper_settings", None)
        if current is None:
            configured = os.getenv("PAPER_CONFIG_PATH")
            with _domain_errors():
                current = await load_agreement_settings(
                    FilePath(configured) if configured else None
                )
            request.app.state.paper_settings = current
        return AgreementMasterSettings.model_validate(current)


async def get_agreement_actor(
    user: Annotated[UserContext, Depends(get_user_context)],
    db: Annotated[AsyncSession, Depends(get_paper_db)],
    settings: Annotated[AgreementMasterSettings, Depends(get_paper_settings)],
) -> AgreementActor:
    """Resolve approval authority from the current tenant's persisted user.

    Args:
        user: Identity from existing authentication.
        db: Host session used for both authorization and master operations.
        settings: Deployment-owned allowed approval roles.

    Returns:
        Trusted actor; synthetic or unrecognized identities cannot approve.
    """
    with _domain_errors():
        try:
            result = await asyncio.wait_for(
                db.execute(
                    select(User).where(User.id == user.user_id, User.tenant_id == user.tenant_id)
                ),
                settings.repository_timeout_seconds,
            )
        except asyncio.TimeoutError:
            raise AgreementMasterError(
                "timeout", "Agreement authorization exceeded its deadline."
            ) from None
    stored = result.scalar_one_or_none()
    allowed = (
        stored is not None
        and stored.tenant_id == user.tenant_id
        and stored.role in settings.approver_roles
    )
    return AgreementActor(tenant_id=user.tenant_id, user_id=user.user_id, can_approve=allowed)


async def get_agreement_service(
    db: Annotated[AsyncSession, Depends(get_paper_db)],
    settings: Annotated[AgreementMasterSettings, Depends(get_paper_settings)],
) -> AgreementMasterService:
    """Inject the SQL adapter without creating inference providers."""
    return AgreementMasterService(SqlAlchemyAgreementRepository(db), settings=settings)


async def _commit(db: AsyncSession) -> None:
    try:
        await asyncio.wait_for(db.commit(), timeout=15)
    except IntegrityError:
        raise AgreementMasterError(
            "conflict", "Agreement mutation conflicts with stored state."
        ) from None
    except asyncio.TimeoutError:
        raise AgreementMasterError("timeout", "Agreement commit exceeded its deadline.") from None


@router.get("/schemas", response_model=tuple[ExternalSchema, ...])
async def list_paper_schemas(
    user: Annotated[UserContext, Depends(get_user_context)],
) -> tuple[ExternalSchema, ...]:
    """Return versioned external schemas for authenticated consumers."""
    return tuple(get_paper_schema(name) for name in PAPER_SCHEMA_NAMES)


@router.get("/schemas/{name}", response_model=ExternalSchema)
async def read_paper_schema(
    name: str,
    user: Annotated[UserContext, Depends(get_user_context)],
    version: Annotated[str, Query(min_length=1, max_length=64)] = "1",
) -> ExternalSchema:
    """Return an external contract suitable for `/v1/extract` schema input."""
    try:
        return get_paper_schema(name, version=version)
    except ValueError:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "schema_not_found",
                "message": "PAPER schema or version was not found.",
            },
        ) from None


@router.post("/agreements", response_model=AgreementVersion, status_code=201)
async def create_agreement(
    body: CreateAgreementRequest,
    actor: Annotated[AgreementActor, Depends(get_agreement_actor)],
    service: Annotated[AgreementMasterService, Depends(get_agreement_service)],
    db: Annotated[AsyncSession, Depends(get_paper_db)],
) -> AgreementVersion:
    """Persist initial unapproved terms in the authenticated tenant."""
    with _domain_errors():
        result = await service.create_draft(actor=actor, identity=body.identity, draft=body.draft)
        await _commit(db)
        return result


@router.get("/agreements", response_model=tuple[AgreementVersion, ...])
async def list_agreements(
    actor: Annotated[AgreementActor, Depends(get_agreement_actor)],
    service: Annotated[AgreementMasterService, Depends(get_agreement_service)],
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> tuple[AgreementVersion, ...]:
    """Read current agreement snapshots within the authenticated tenant.

    Args:
        actor: Server-established tenant identity.
        service: Injected agreement lifecycle and read service.
        limit: Page size between one and 100.
        offset: Nonnegative number of agreements to skip.

    Returns:
        One latest version per agreement, most recently revised first.
    """
    with _domain_errors():
        return await service.list_agreements(actor=actor, limit=limit, offset=offset)


@router.get("/agreements/approved", response_model=AgreementVersion)
async def find_approved_agreement(
    vendor_id: Annotated[str, Query(min_length=1, max_length=128, pattern=r"\S")],
    store_id: Annotated[str, Query(min_length=1, max_length=128, pattern=r"\S")],
    contract_number: Annotated[str, Query(min_length=1, max_length=128, pattern=r"\S")],
    as_of: date,
    actor: Annotated[AgreementActor, Depends(get_agreement_actor)],
    service: Annotated[AgreementMasterService, Depends(get_agreement_service)],
) -> AgreementVersion:
    """Read approved effective reference data; return 404 when there is no match."""
    lookup = AgreementLookup(
        identity=AgreementIdentity(
            vendor_id=vendor_id, store_id=store_id, contract_number=contract_number
        ),
        as_of=as_of,
    )
    with _domain_errors():
        result = await service.find_approved(actor=actor, lookup=lookup)
        if result is None:
            raise AgreementMasterError("not_found", "No approved effective agreement was found.")
        return result


@router.post(
    "/agreements/{agreement_id}/versions", response_model=AgreementVersion, status_code=201
)
async def revise_agreement(
    agreement_id: Annotated[str, Path(min_length=1, max_length=128, pattern=r"\S")],
    body: ReviseAgreementRequest,
    actor: Annotated[AgreementActor, Depends(get_agreement_actor)],
    service: Annotated[AgreementMasterService, Depends(get_agreement_service)],
    db: Annotated[AsyncSession, Depends(get_paper_db)],
) -> AgreementVersion:
    """Append terms with an expected-version guard; preserve prior snapshots."""
    with _domain_errors():
        result = await service.revise(
            actor=actor,
            agreement_id=agreement_id,
            expected_version=body.expected_version,
            draft=body.draft,
        )
        await _commit(db)
        return result


@router.get("/agreements/{agreement_id}/versions", response_model=tuple[AgreementVersion, ...])
async def list_agreement_versions(
    agreement_id: Annotated[str, Path(min_length=1, max_length=128, pattern=r"\S")],
    actor: Annotated[AgreementActor, Depends(get_agreement_actor)],
    service: Annotated[AgreementMasterService, Depends(get_agreement_service)],
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> tuple[AgreementVersion, ...]:
    """Read paginated draft and approved history within the current tenant."""
    with _domain_errors():
        return await service.list_versions(
            actor=actor, agreement_id=agreement_id, limit=limit, offset=offset
        )


@router.get("/agreements/{agreement_id}/versions/{version_number}", response_model=AgreementVersion)
async def read_agreement_version(
    agreement_id: Annotated[str, Path(min_length=1, max_length=128, pattern=r"\S")],
    version_number: Annotated[int, Path(ge=1)],
    actor: Annotated[AgreementActor, Depends(get_agreement_actor)],
    service: Annotated[AgreementMasterService, Depends(get_agreement_service)],
) -> AgreementVersion:
    """Read the exact historical version without selecting another tenant."""
    with _domain_errors():
        return await service.get_version(
            actor=actor, agreement_id=agreement_id, version_number=version_number
        )


@router.post(
    "/agreements/{agreement_id}/versions/{version_number}/approval", response_model=AgreementVersion
)
async def approve_agreement_version(
    agreement_id: Annotated[str, Path(min_length=1, max_length=128, pattern=r"\S")],
    version_number: Annotated[int, Path(ge=1)],
    body: ApprovalDecision,
    actor: Annotated[AgreementActor, Depends(get_agreement_actor)],
    service: Annotated[AgreementMasterService, Depends(get_agreement_service)],
    db: Annotated[AsyncSession, Depends(get_paper_db)],
) -> AgreementVersion:
    """Publish the reviewed latest version using server-resolved approval authority."""
    with _domain_errors():
        if not actor.can_approve:
            raise AgreementMasterError("forbidden", "Agreement approval authority is required.")
        result = await service.approve(
            actor=actor, agreement_id=agreement_id, version_number=version_number, decision=body
        )
        await _commit(db)
        return result
