"""Authenticated read-only navigation over existing PAPER workflows and history."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth import UserContext, get_user_context
from src.api.paper_routes import _domain_errors, _rate_limit, get_paper_db
from src.paper.workspace.contracts import (
    WorkspaceCase,
    WorkspaceContract,
    WorkspaceDocument,
    WorkspacePage,
    WorkspaceQuery,
)
from src.services.paper_workspace_index import PaperWorkspaceIndexService

router = APIRouter(
    prefix="/v1/paper/workspace", tags=["paper-workspace"], dependencies=[Depends(_rate_limit)]
)
_Search = Annotated[str, Query(max_length=200)]
_Limit = Annotated[int, Query(ge=1, le=100)]
_Offset = Annotated[int, Query(ge=0)]
_Reference = Annotated[str | None, Query(min_length=1, max_length=128, pattern=r"\S")]


async def get_workspace_index(
    db: Annotated[AsyncSession, Depends(get_paper_db)],
) -> PaperWorkspaceIndexService:
    """Inject tenant-scoped read projection; no inference providers or write methods."""
    return PaperWorkspaceIndexService(db)


@router.get("/cases", response_model=WorkspacePage[WorkspaceCase])
async def list_workspace_cases(
    user: Annotated[UserContext, Depends(get_user_context)],
    service: Annotated[PaperWorkspaceIndexService, Depends(get_workspace_index)],
    q: _Search = "",
    status: (
        Literal[
            "approved",
            "rejected",
            "duplicate",
            "matched",
            "incomplete",
            "mismatched",
            "needs_review",
        ]
        | None
    ) = None,
    agreement_id: _Reference = None,
    association_kind: Literal["confirmed", "legacy_identity"] = "confirmed",
    limit: _Limit = 20,
    offset: _Offset = 0,
) -> WorkspacePage[WorkspaceCase]:
    """Search latest cases and explicit contract links before deterministic pagination."""
    with _domain_errors():
        return await service.cases(
            user.tenant_id,
            WorkspaceQuery(
                q=q,
                status=status,
                agreement_id=agreement_id,
                association_kind=association_kind,
                limit=limit,
                offset=offset,
            ),
        )


@router.get("/contracts", response_model=WorkspacePage[WorkspaceContract])
async def list_workspace_contracts(
    user: Annotated[UserContext, Depends(get_user_context)],
    service: Annotated[PaperWorkspaceIndexService, Depends(get_workspace_index)],
    q: _Search = "",
    status: Literal["draft", "approved"] | None = None,
    limit: _Limit = 20,
    offset: _Offset = 0,
) -> WorkspacePage[WorkspaceContract]:
    """Search latest contract versions, prior approval and separate invoice link counts."""
    with _domain_errors():
        return await service.contracts(
            user.tenant_id, WorkspaceQuery(q=q, status=status, limit=limit, offset=offset)
        )


@router.get("/documents", response_model=WorkspacePage[WorkspaceDocument])
async def list_workspace_documents(
    user: Annotated[UserContext, Depends(get_user_context)],
    service: Annotated[PaperWorkspaceIndexService, Depends(get_workspace_index)],
    q: _Search = "",
    status: Literal["pending", "processing", "completed", "failed"] | None = None,
    workflow_status: (
        Literal[
            "processing",
            "extraction_failed",
            "ready_for_review",
            "agreement_draft",
            "agreement_approved",
            "invoice_case",
        ]
        | None
    ) = None,
    job_id: _Reference = None,
    archived: bool = False,
    limit: _Limit = 20,
    offset: _Offset = 0,
) -> WorkspacePage[WorkspaceDocument]:
    """Search upload status and exact source links; exact job lookup includes archives.

    Archived attempts remain readable and unmodified. Links are bounded to twenty per
    source, with workflow_links_total indicating any additional related workflows.
    """
    with _domain_errors():
        return await service.documents(
            user.tenant_id,
            WorkspaceQuery(
                q=q,
                status=status,
                workflow_status=workflow_status,
                job_id=job_id,
                archived=archived,
                limit=limit,
                offset=offset,
            ),
        )
