"""Async draft persistence preserves history and applies filtering before paging."""

from datetime import timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.paper_document_draft import PaperDocumentDraft
from src.db.models.paper_document_draft_version import PaperDocumentDraftVersion
from src.paper.contracts import AgreementActor
from src.paper.drafts.create_request import CreateDocumentDraftRequest
from src.paper.drafts.query import DocumentDraftQuery
from src.paper.drafts.revise_request import ReviseDocumentDraftRequest
from src.paper.errors import AgreementMasterError
from src.services.paper_document_draft_repository import SqlAlchemyDocumentDraftRepository
from src.services.paper_document_drafts import DocumentDraftService
from tests.integration.test_paper_agreement_master import db as agreement_db

db = agreement_db


def _actor(tenant: str = "tenant-a") -> AgreementActor:
    return AgreementActor(tenant_id=tenant, user_id="reviewer")


def _request(*, number: str = "INV_100%", reviewed: bool = True) -> CreateDocumentDraftRequest:
    return CreateDocumentDraftRequest.model_validate(
        {
            "role": "rent_invoice",
            "document": {"source_document_id": "original", "fields": {"invoice_number": number}},
            "reviewed": reviewed,
            "reason": "Checked source",
        }
    )


@pytest.mark.asyncio
async def test_reviewed_draft_revise_clears_review_and_preserves_exact_history(
    db: AsyncSession,
) -> None:
    service = DocumentDraftService(SqlAlchemyDocumentDraftRepository(db))
    first = await service.create(actor=_actor(), request=_request())
    assert first.status == "reviewed"
    assert first.reviewed_by == "reviewer" and first.reviewed_at == first.created_at
    second = await service.revise(
        actor=_actor(),
        draft_id=first.draft_id,
        request=ReviseDocumentDraftRequest(
            **_request(reviewed=False).model_dump(),
            expected_version=1,
        ),
    )
    assert second.version_number == 2 and second.status == "draft"
    assert second.reviewed_at is None and second.reviewed_by is None
    retained = await service.get_version(actor=_actor(), draft_id=first.draft_id, version_number=1)
    assert retained == first
    assert retained.created_at.tzinfo == timezone.utc
    history = await service.list_versions(actor=_actor(), draft_id=first.draft_id, limit=1)
    assert history.total == 2 and history.items == (second,)
    with pytest.raises(AgreementMasterError) as caught:
        await service.revise(
            actor=_actor(),
            draft_id=first.draft_id,
            request=ReviseDocumentDraftRequest(
                **_request().model_dump(),
                expected_version=1,
            ),
        )
    assert caught.value.code == "conflict"
    assert (await service.list_versions(actor=_actor(), draft_id=first.draft_id)).total == 2


@pytest.mark.asyncio
async def test_tenant_isolation_and_literal_search_filters_before_paging(db: AsyncSession) -> None:
    service = DocumentDraftService(SqlAlchemyDocumentDraftRepository(db))
    first = await service.create(actor=_actor(), request=_request())
    await service.create(actor=_actor(), request=_request(number="INVA1000"))
    await service.create(actor=_actor(), request=_request(number="INV-DRAFT", reviewed=False))
    await service.create(actor=_actor("tenant-b"), request=_request())
    page = await service.list_latest(
        actor=_actor(), query=DocumentDraftQuery(q="_100%", status="reviewed", limit=1)
    )
    assert page.total == 1 and page.items[0].draft_id == first.draft_id
    assert (
        await service.list_latest(actor=_actor(), query=DocumentDraftQuery(status="draft"))
    ).total == 1
    with pytest.raises(AgreementMasterError) as caught:
        await service.get_version(
            actor=_actor("tenant-b"), draft_id=first.draft_id, version_number=1
        )
    assert caught.value.code == "not_found"


@pytest.mark.asyncio
async def test_orm_snapshots_and_header_identity_are_immutable(db: AsyncSession) -> None:
    result = await DocumentDraftService(SqlAlchemyDocumentDraftRepository(db)).create(
        actor=_actor(), request=_request()
    )
    snapshot = (await db.execute(select(PaperDocumentDraftVersion))).scalar_one()
    snapshot.reason = "rewritten history"
    with pytest.raises(ValueError, match="immutable"):
        await db.flush()
    await db.rollback()
    assert result.version_number == 1


@pytest.mark.asyncio
async def test_role_change_is_atomic_and_does_not_advance_header(db: AsyncSession) -> None:
    repository = SqlAlchemyDocumentDraftRepository(db)
    first = await repository.create(actor=_actor(), request=_request())
    with pytest.raises(AgreementMasterError):
        await repository.append(
            actor=_actor(),
            draft_id=first.draft_id,
            request=ReviseDocumentDraftRequest(
                expected_version=1,
                role="tax_invoice",
                document={"source_document_id": "source", "fields": {}},
                reason="Changed role",
            ),
        )
    row = (await db.execute(select(PaperDocumentDraft))).scalar_one()
    await db.refresh(row)
    assert row.latest_version == 1
