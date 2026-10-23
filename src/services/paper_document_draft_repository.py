"""Async SQLAlchemy adapter for independent, immutable PAPER source drafts."""

from datetime import datetime, timezone
from typing import Annotated, Any, cast
from uuid import uuid4

from pydantic import Field, TypeAdapter, ValidationError
from sqlalchemy import Select, and_, func, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.paper_document_draft import PaperDocumentDraft
from src.db.models.paper_document_draft_version import PaperDocumentDraftVersion
from src.paper.contracts import AgreementActor
from src.paper.contracts._base import Identifier
from src.paper.drafts.create_request import CreateDocumentDraftRequest
from src.paper.drafts.page import DocumentDraftPage
from src.paper.drafts.query import DocumentDraftQuery
from src.paper.drafts.repository import BaseDocumentDraftRepository
from src.paper.drafts.revise_request import ReviseDocumentDraftRequest
from src.paper.drafts.version import DocumentDraftVersion
from src.paper.errors import AgreementMasterError

_IDENTIFIER: TypeAdapter[str] = TypeAdapter(Identifier)
_VERSION: TypeAdapter[int] = TypeAdapter(Annotated[int, Field(ge=1, strict=True)])


def _reference(value: str) -> str:
    try:
        return _IDENTIFIER.validate_python(value)
    except ValidationError:
        raise AgreementMasterError(
            "invalid_agreement", "Document draft reference is invalid."
        ) from None


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


class SqlAlchemyDocumentDraftRepository(BaseDocumentDraftRepository):
    """Append snapshots atomically while the embedding host owns commit and rollback."""

    def __init__(self, db: AsyncSession) -> None:
        """Inject a host-owned async database session."""
        self._db = db

    async def create(
        self, *, actor: AgreementActor, request: CreateDocumentDraftRequest
    ) -> DocumentDraftVersion:
        """Save initial source fields and server-stamped review provenance atomically."""
        actor = AgreementActor.model_validate(actor)
        request = CreateDocumentDraftRequest.model_validate(request.model_dump(mode="json"))
        now = datetime.now(timezone.utc)
        header = PaperDocumentDraft(
            id=str(uuid4()),
            tenant_id=actor.tenant_id,
            role=request.role,
            latest_version=1,
            created_at=now,
        )
        snapshot = self._snapshot(actor, header.id, 1, request, now)
        try:
            async with self._db.begin_nested():
                self._db.add(header)
                await self._db.flush()
                self._db.add(snapshot)
                await self._db.flush()
        except IntegrityError:
            raise AgreementMasterError("conflict", "Document draft could not be saved.") from None
        return self._materialize(header, snapshot)

    async def append(
        self, *, actor: AgreementActor, draft_id: str, request: ReviseDocumentDraftRequest
    ) -> DocumentDraftVersion:
        """Compare-and-swap latest version and append one immutable correction."""
        actor = AgreementActor.model_validate(actor)
        draft_id = _reference(draft_id)
        request = ReviseDocumentDraftRequest.model_validate(request.model_dump(mode="json"))
        snapshot = self._snapshot(
            actor, draft_id, request.expected_version + 1, request, datetime.now(timezone.utc)
        )
        try:
            async with self._db.begin_nested():
                result = cast(
                    CursorResult[Any],
                    await self._db.execute(
                        update(PaperDocumentDraft)
                        .where(
                            PaperDocumentDraft.tenant_id == actor.tenant_id,
                            PaperDocumentDraft.id == draft_id,
                            PaperDocumentDraft.role == request.role,
                            PaperDocumentDraft.latest_version == request.expected_version,
                        )
                        .values(latest_version=request.expected_version + 1)
                        .execution_options(synchronize_session=False)
                    ),
                )
                if result.rowcount != 1:
                    raise AgreementMasterError(
                        "conflict", "Document draft revision is stale or unavailable."
                    )
                self._db.add(snapshot)
                await self._db.flush()
        except IntegrityError:
            raise AgreementMasterError(
                "conflict", "Document draft revision could not be saved."
            ) from None
        return DocumentDraftVersion(
            draft_id=draft_id,
            tenant_id=actor.tenant_id,
            role=request.role,
            version_number=snapshot.version_number,
            document=request.document,
            status="reviewed" if request.reviewed else "draft",
            created_by=actor.user_id,
            created_at=_aware(snapshot.created_at),
            reason=request.reason,
            reviewed_by=snapshot.reviewed_by,
            reviewed_at=_aware(snapshot.reviewed_at) if snapshot.reviewed_at else None,
        )

    async def get_version(
        self, *, tenant_id: str, draft_id: str, version_number: int
    ) -> DocumentDraftVersion | None:
        """Read a source snapshot only through its exact tenant and version key."""
        tenant_id, draft_id = _reference(tenant_id), _reference(draft_id)
        try:
            version_number = _VERSION.validate_python(version_number)
        except ValidationError:
            raise AgreementMasterError(
                "invalid_agreement", "Document draft version is invalid."
            ) from None
        result = await self._db.execute(
            self._query().where(
                PaperDocumentDraft.tenant_id == tenant_id,
                PaperDocumentDraft.id == draft_id,
                PaperDocumentDraftVersion.version_number == version_number,
            )
        )
        row = result.first()
        return self._materialize(row[0], row[1]) if row else None

    async def list_latest(self, *, tenant_id: str, query: DocumentDraftQuery) -> DocumentDraftPage:
        """Apply literal search, role and latest-status filters before pagination."""
        tenant_id = _reference(tenant_id)
        query = DocumentDraftQuery.model_validate(query)
        statement = self._query().where(
            PaperDocumentDraft.tenant_id == tenant_id,
            PaperDocumentDraft.latest_version == PaperDocumentDraftVersion.version_number,
        )
        if query.role:
            statement = statement.where(PaperDocumentDraft.role == query.role)
        if query.status:
            statement = statement.where(PaperDocumentDraftVersion.status == query.status)
        if query.q.strip():
            statement = statement.where(
                PaperDocumentDraftVersion.search_text.icontains(query.q.strip(), autoescape=True)
            )
        return await self._page(
            statement.order_by(PaperDocumentDraft.created_at.desc(), PaperDocumentDraft.id.desc()),
            query.limit,
            query.offset,
        )

    async def list_versions(
        self, *, tenant_id: str, draft_id: str, limit: int, offset: int
    ) -> DocumentDraftPage:
        """Read immutable tenant-qualified history with a scoped total count."""
        tenant_id, draft_id = _reference(tenant_id), _reference(draft_id)
        page = DocumentDraftQuery(limit=limit, offset=offset)
        return await self._page(
            self._query()
            .where(
                PaperDocumentDraft.tenant_id == tenant_id,
                PaperDocumentDraft.id == draft_id,
            )
            .order_by(PaperDocumentDraftVersion.version_number.desc()),
            page.limit,
            page.offset,
        )

    async def _page(
        self,
        statement: Select[tuple[PaperDocumentDraft, PaperDocumentDraftVersion]],
        limit: int,
        offset: int,
    ) -> DocumentDraftPage:
        count = await self._db.execute(
            select(func.count()).select_from(statement.order_by(None).subquery())
        )
        result = await self._db.execute(statement.limit(limit).offset(offset))
        return DocumentDraftPage(
            items=tuple(self._materialize(row[0], row[1]) for row in result.all()),
            total=count.scalar_one(),
            limit=limit,
            offset=offset,
        )

    @staticmethod
    def _query() -> Select[tuple[PaperDocumentDraft, PaperDocumentDraftVersion]]:
        return select(PaperDocumentDraft, PaperDocumentDraftVersion).join(
            PaperDocumentDraftVersion,
            and_(
                PaperDocumentDraft.tenant_id == PaperDocumentDraftVersion.tenant_id,
                PaperDocumentDraft.id == PaperDocumentDraftVersion.draft_id,
            ),
        )

    @staticmethod
    def _snapshot(
        actor: AgreementActor,
        draft_id: str,
        version: int,
        request: CreateDocumentDraftRequest,
        now: datetime,
    ) -> PaperDocumentDraftVersion:
        data = request.document.model_dump(mode="json")
        fields = data["fields"]
        search = [draft_id, request.role, request.document.source_document_id]
        search.extend(
            str(fields[key])
            for key in (
                "vendor_name",
                "invoice_number",
                "tax_invoice_number",
                "reference_number",
                "contract_number",
                "location",
                "document_type",
            )
            if fields.get(key) is not None
        )
        return PaperDocumentDraftVersion(
            tenant_id=actor.tenant_id,
            draft_id=draft_id,
            version_number=version,
            document=data,
            status="reviewed" if request.reviewed else "draft",
            search_text=" ".join(search),
            created_by=actor.user_id,
            created_at=now,
            reason=request.reason,
            reviewed_by=actor.user_id if request.reviewed else None,
            reviewed_at=now if request.reviewed else None,
        )

    @staticmethod
    def _materialize(
        header: PaperDocumentDraft, snapshot: PaperDocumentDraftVersion
    ) -> DocumentDraftVersion:
        return DocumentDraftVersion.model_validate(
            {
                "draft_id": header.id,
                "tenant_id": header.tenant_id,
                "role": header.role,
                "version_number": snapshot.version_number,
                "document": snapshot.document,
                "status": snapshot.status,
                "created_by": snapshot.created_by,
                "created_at": _aware(snapshot.created_at),
                "reason": snapshot.reason,
                "reviewed_by": snapshot.reviewed_by,
                "reviewed_at": _aware(snapshot.reviewed_at) if snapshot.reviewed_at else None,
            }
        )
