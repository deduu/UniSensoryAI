"""Authenticated source review persistence, independent of case assessment."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth import UserContext, get_user_context
from src.api.paper_routes import _commit, _domain_errors, _rate_limit, get_paper_db
from src.paper.contracts import AgreementActor
from src.paper.drafts.content import DocumentRole
from src.paper.drafts.create_request import CreateDocumentDraftRequest
from src.paper.drafts.page import DocumentDraftPage
from src.paper.drafts.query import DocumentDraftQuery
from src.paper.drafts.revise_request import ReviseDocumentDraftRequest
from src.paper.drafts.version import DocumentDraftVersion
from src.services.paper_document_draft_repository import SqlAlchemyDocumentDraftRepository
from src.services.paper_document_drafts import DocumentDraftService

router = APIRouter(
    prefix="/v1/paper/document-drafts",
    tags=["paper-document-drafts"],
    dependencies=[Depends(_rate_limit)],
)
_Reference = Annotated[str, Path(min_length=1, max_length=128, pattern=r"\S")]
_Limit = Annotated[int, Query(ge=1, le=100)]
_Offset = Annotated[int, Query(ge=0)]


async def get_document_draft_service(
    db: Annotated[AsyncSession, Depends(get_paper_db)],
) -> DocumentDraftService:
    """Inject source review storage in the host transaction without a model dependency."""
    return DocumentDraftService(SqlAlchemyDocumentDraftRepository(db))


def _actor(user: UserContext) -> AgreementActor:
    return AgreementActor(tenant_id=user.tenant_id, user_id=user.user_id)


@router.post("", response_model=DocumentDraftVersion, status_code=201)
async def create_document_draft(
    body: CreateDocumentDraftRequest,
    user: Annotated[UserContext, Depends(get_user_context)],
    service: Annotated[DocumentDraftService, Depends(get_document_draft_service)],
    db: Annotated[AsyncSession, Depends(get_paper_db)],
) -> DocumentDraftVersion:
    """Save reviewed or incomplete source fields without executing reconciliation."""
    with _domain_errors():
        result = await service.create(actor=_actor(user), request=body)
        await _commit(db)
        return result


@router.get("", response_model=DocumentDraftPage)
async def list_document_drafts(
    user: Annotated[UserContext, Depends(get_user_context)],
    service: Annotated[DocumentDraftService, Depends(get_document_draft_service)],
    q: Annotated[str, Query(max_length=200)] = "",
    role: DocumentRole | None = None,
    status: Literal["draft", "reviewed"] | None = None,
    limit: _Limit = 20,
    offset: _Offset = 0,
) -> DocumentDraftPage:
    """Search latest source drafts by role and review status before pagination."""
    with _domain_errors():
        return await service.list_latest(
            actor=_actor(user),
            query=DocumentDraftQuery(q=q, role=role, status=status, limit=limit, offset=offset),
        )


@router.post("/{draft_id}/versions", response_model=DocumentDraftVersion, status_code=201)
async def revise_document_draft(
    draft_id: _Reference,
    body: ReviseDocumentDraftRequest,
    user: Annotated[UserContext, Depends(get_user_context)],
    service: Annotated[DocumentDraftService, Depends(get_document_draft_service)],
    db: Annotated[AsyncSession, Depends(get_paper_db)],
) -> DocumentDraftVersion:
    """Append corrected fields; preserve all prior source and review snapshots."""
    with _domain_errors():
        result = await service.revise(actor=_actor(user), draft_id=draft_id, request=body)
        await _commit(db)
        return result


@router.get("/{draft_id}/versions", response_model=DocumentDraftPage)
async def list_document_draft_versions(
    draft_id: _Reference,
    user: Annotated[UserContext, Depends(get_user_context)],
    service: Annotated[DocumentDraftService, Depends(get_document_draft_service)],
    limit: _Limit = 100,
    offset: _Offset = 0,
) -> DocumentDraftPage:
    """Read immutable tenant-qualified source review history, newest first."""
    with _domain_errors():
        return await service.list_versions(
            actor=_actor(user), draft_id=draft_id, limit=limit, offset=offset
        )


@router.get("/{draft_id}/versions/{version_number}", response_model=DocumentDraftVersion)
async def read_document_draft_version(
    draft_id: _Reference,
    version_number: Annotated[int, Path(ge=1)],
    user: Annotated[UserContext, Depends(get_user_context)],
    service: Annotated[DocumentDraftService, Depends(get_document_draft_service)],
) -> DocumentDraftVersion:
    """Read the exact selected source version; missing versions never fall back."""
    with _domain_errors():
        return await service.get_version(
            actor=_actor(user), draft_id=draft_id, version_number=version_number
        )
