"""Model-independent source review lifecycle without reconciliation side effects."""

import asyncio
from collections.abc import Awaitable
from typing import TypeVar

import structlog
from pydantic import Field

from src.paper.contracts import AgreementActor
from src.paper.contracts._base import Identifier, _Contract
from src.paper.drafts.create_request import CreateDocumentDraftRequest
from src.paper.drafts.page import DocumentDraftPage
from src.paper.drafts.query import DocumentDraftQuery
from src.paper.drafts.repository import BaseDocumentDraftRepository
from src.paper.drafts.revise_request import ReviseDocumentDraftRequest
from src.paper.drafts.version import DocumentDraftVersion
from src.paper.errors import AgreementMasterError

_T = TypeVar("_T")
_logger = structlog.get_logger(__name__)


class _Reference(_Contract):
    draft_id: Identifier
    version_number: int = Field(ge=1, strict=True)


class DocumentDraftService:
    """Save incomplete or reviewed source snapshots through injected async storage."""

    def __init__(self, repository: BaseDocumentDraftRepository) -> None:
        """Inject storage; this lifecycle has no model or reconciliation dependency."""
        self._repository = repository

    @staticmethod
    async def _run(operation: Awaitable[_T]) -> _T:
        try:
            return await asyncio.wait_for(operation, timeout=15)
        except asyncio.TimeoutError:
            raise AgreementMasterError(
                "timeout", "Document draft storage exceeded its deadline."
            ) from None

    @staticmethod
    def _scoped(result: DocumentDraftVersion, actor: AgreementActor) -> DocumentDraftVersion:
        result = DocumentDraftVersion.model_validate(result.model_dump(mode="json"))
        if result.tenant_id != actor.tenant_id:
            raise AgreementMasterError("not_found", "Document draft was not found.")
        return result

    async def create(
        self, *, actor: AgreementActor, request: CreateDocumentDraftRequest
    ) -> DocumentDraftVersion:
        """Save source values and server-attested review intent, without matching."""
        actor = AgreementActor.model_validate(actor)
        request = CreateDocumentDraftRequest.model_validate(request.model_dump(mode="json"))
        result = self._scoped(
            await self._run(self._repository.create(actor=actor, request=request)), actor
        )
        _logger.info(
            "paper_document_draft_created",
            draft_id=result.draft_id,
            version=result.version_number,
            reviewed=result.status == "reviewed",
        )
        return result

    async def revise(
        self, *, actor: AgreementActor, draft_id: str, request: ReviseDocumentDraftRequest
    ) -> DocumentDraftVersion:
        """Append a correction; review is reset unless explicitly requested again."""
        actor = AgreementActor.model_validate(actor)
        request = ReviseDocumentDraftRequest.model_validate(request.model_dump(mode="json"))
        previous = await self.get_version(
            actor=actor, draft_id=draft_id, version_number=request.expected_version
        )
        if previous.role != request.role:
            raise AgreementMasterError("conflict", "Document draft role cannot change.")
        result = self._scoped(
            await self._run(
                self._repository.append(actor=actor, draft_id=previous.draft_id, request=request)
            ),
            actor,
        )
        _logger.info(
            "paper_document_draft_revised",
            draft_id=result.draft_id,
            version=result.version_number,
            reviewed=result.status == "reviewed",
        )
        return result

    async def get_version(
        self, *, actor: AgreementActor, draft_id: str, version_number: int
    ) -> DocumentDraftVersion:
        """Read an exact tenant-owned version; never substitute the latest version."""
        actor = AgreementActor.model_validate(actor)
        reference = _Reference(draft_id=draft_id, version_number=version_number)
        result = await self._run(
            self._repository.get_version(
                tenant_id=actor.tenant_id,
                draft_id=reference.draft_id,
                version_number=reference.version_number,
            )
        )
        if (
            result is None
            or result.tenant_id != actor.tenant_id
            or result.draft_id != reference.draft_id
            or result.version_number != reference.version_number
        ):
            raise AgreementMasterError("not_found", "Document draft version was not found.")
        return self._scoped(result, actor)

    async def list_latest(
        self, *, actor: AgreementActor, query: DocumentDraftQuery
    ) -> DocumentDraftPage:
        """List current drafts with server-side filtering before paging."""
        actor = AgreementActor.model_validate(actor)
        query = DocumentDraftQuery.model_validate(query)
        result = await self._run(
            self._repository.list_latest(tenant_id=actor.tenant_id, query=query)
        )
        for item in result.items:
            self._scoped(item, actor)
        return DocumentDraftPage.model_validate(result)

    async def list_versions(
        self, *, actor: AgreementActor, draft_id: str, limit: int = 100, offset: int = 0
    ) -> DocumentDraftPage:
        """Read immutable draft history, newest first, within the current tenant."""
        actor = AgreementActor.model_validate(actor)
        page = DocumentDraftQuery(limit=limit, offset=offset)
        first = await self.get_version(actor=actor, draft_id=draft_id, version_number=1)
        result = await self._run(
            self._repository.list_versions(
                tenant_id=actor.tenant_id,
                draft_id=first.draft_id,
                limit=page.limit,
                offset=page.offset,
            )
        )
        for item in result.items:
            self._scoped(item, actor)
            if item.draft_id != first.draft_id:
                raise AgreementMasterError("not_found", "Document draft history was not found.")
        return DocumentDraftPage.model_validate(result)
