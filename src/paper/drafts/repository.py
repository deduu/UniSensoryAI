"""Async persistence port for source review, separate from case assessment."""

from abc import ABC, abstractmethod

from src.paper.contracts import AgreementActor

from .create_request import CreateDocumentDraftRequest
from .page import DocumentDraftPage
from .query import DocumentDraftQuery
from .revise_request import ReviseDocumentDraftRequest
from .version import DocumentDraftVersion


class BaseDocumentDraftRepository(ABC):
    """Tenant-scoped immutable storage; the embedding host owns transactions."""

    @abstractmethod
    async def create(
        self, *, actor: AgreementActor, request: CreateDocumentDraftRequest
    ) -> DocumentDraftVersion:
        """Store version one with trusted author and review provenance."""

    @abstractmethod
    async def append(
        self, *, actor: AgreementActor, draft_id: str, request: ReviseDocumentDraftRequest
    ) -> DocumentDraftVersion:
        """Atomically append only when the expected version and role still match."""

    @abstractmethod
    async def get_version(
        self, *, tenant_id: str, draft_id: str, version_number: int
    ) -> DocumentDraftVersion | None:
        """Read only the exact requested tenant-owned snapshot."""

    @abstractmethod
    async def list_latest(self, *, tenant_id: str, query: DocumentDraftQuery) -> DocumentDraftPage:
        """Apply role, status and literal search before deterministic paging."""

    @abstractmethod
    async def list_versions(
        self, *, tenant_id: str, draft_id: str, limit: int, offset: int
    ) -> DocumentDraftPage:
        """Read retained history newest first with its complete scoped count."""
