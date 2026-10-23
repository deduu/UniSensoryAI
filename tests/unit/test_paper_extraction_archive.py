"""Recoverable extraction cleanup preserves source evidence and ingestion history."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import FastAPI
from pydantic import ValidationError
from sqlalchemy import event, select
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from src.api.auth import UserContext, get_user_context
from src.api.paper_extraction_routes import (
    _db_session,
    get_history_service,
    get_page_preview_service,
    router,
)
from src.db.base import Base
from src.db.models.document import Document
from src.db.models.ingestion import IngestionJob, IngestionStatus
from src.db.models.tenant import Tenant
from src.extraction.contracts import DocumentResult, PageContent
from src.paper.contracts import (
    AgreementActor,
    AgreementDraft,
    AgreementIdentity,
    AgreementLookup,
    ApprovalDecision,
)
from src.paper.extraction_archive_error import PaperExtractionArchiveError
from src.paper.extraction_contracts import PaperExtractionJob, PaperExtractionResult
from src.paper.extraction_contracts.archive_request import ExtractionArchiveRequest
from src.paper.schemas import RentAgreementSchema
from src.services.agreement_repository import SqlAlchemyAgreementRepository
from src.services.paper_extraction_history import PaperExtractionHistoryService

_NOW = datetime(2026, 10, 17, tzinfo=timezone.utc)
_SOURCE_ID = "c" * 64


@asynccontextmanager
async def _database() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", poolclass=StaticPool)

    @event.listens_for(engine.sync_engine, "connect")
    def enable_transactions(connection: object, _: object) -> None:
        connection.isolation_level = None  # type: ignore[attr-defined]

    @event.listens_for(engine.sync_engine, "begin")
    def begin_transaction(connection: Connection) -> None:
        connection.exec_driver_sql("BEGIN")

    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        maker = async_sessionmaker(engine, expire_on_commit=False)
        async with maker() as db:
            db.add_all(
                [
                    Tenant(id="tenant-a", name="A", slug="a"),
                    Tenant(id="tenant-b", name="B", slug="b"),
                ]
            )
            await db.commit()
            yield db
    finally:
        await engine.dispose()


async def _store(
    db: AsyncSession,
    root: Path,
    job_id: str,
    *,
    tenant_id: str = "tenant-a",
    workflow: str = "paper_extraction",
    status: IngestionStatus = IngestionStatus.COMPLETED,
) -> IngestionJob:
    result = PaperExtractionResult(
        document=DocumentResult(
            document_id=_SOURCE_ID,
            source_name="contract.pdf",
            content_mode="text",
            text="Exact retained source text",
            pages=(PageContent(page_number=1, width=100, height=100),),
        )
    )
    await asyncio.to_thread((root / f"{job_id}.pdf").write_bytes, b"%PDF-1.7\noriginal")
    await asyncio.to_thread(
        (root / f"{job_id}.json").write_text, result.model_dump_json(), encoding="utf-8"
    )
    job = IngestionJob(
        id=job_id,
        tenant_id=tenant_id,
        file_path=f"{job_id}.pdf",
        status=status,
        created_at=_NOW,
        updated_at=_NOW,
        meta={
            "workflow": workflow,
            "schema_name": "rent_agreement",
            "original_filename": "contract.pdf",
            "document_id": _SOURCE_ID,
            "model_ids": ["independent-model"],
            "usage": {
                "version": "1",
                "calls": [],
                "call_count": 0,
                "measured_call_count": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "estimated_cost": None,
                "currency": None,
                "coverage": "complete",
                "cost_coverage": "unavailable",
            },
        },
    )
    db.add(job)
    db.add(
        Document(
            id=f"doc-{job_id}",
            tenant_id=tenant_id,
            job_id=job_id,
            filename="contract.pdf",
            content_text="Retained document content",
            content_chunks=[
                {"type": "paper_extraction_artifact", "artifact_name": f"{job_id}.json"}
            ],
        )
    )
    await db.commit()
    return job


def _request(*job_ids: str, archived: bool = True) -> ExtractionArchiveRequest:
    return ExtractionArchiveRequest(job_ids=job_ids, archived=archived)


@pytest.mark.parametrize(
    "values",
    [
        {"job_ids": [], "archived": True},
        {"job_ids": ["same", "same"], "archived": True},
        {"job_ids": [f"job-{index}" for index in range(101)], "archived": True},
        {"job_ids": ["../private"], "archived": True},
        {"job_ids": ["job-1"], "archived": "yes"},
        {"job_ids": ["job-1"], "archived": True, "tenant_id": "tenant-b"},
    ],
)
def test_archive_request_validates_identifiers_scope_and_explicit_action(
    values: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        ExtractionArchiveRequest.model_validate(values)


@pytest.mark.asyncio
async def test_archive_hides_attempts_without_changing_originals_usage_or_source_reads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("UPLOADS_DIR", str(tmp_path))
    async with _database() as db:
        old = await _store(db, tmp_path, "old")
        await _store(db, tmp_path, "replacement")
        metadata = dict(old.meta or {})
        original = await asyncio.to_thread((tmp_path / "old.pdf").read_bytes)
        artifact = await asyncio.to_thread((tmp_path / "old.json").read_bytes)
        service = PaperExtractionHistoryService(db)
        changed = await service.set_archived(_request("old"), "tenant-a", user_id="reviewer")
        await db.commit()
        assert [item.job_id for item in changed] == ["old"]
        assert changed[0].archived is True and changed[0].archived_by == "reviewer"
        assert changed[0].archived_at is not None
        assert changed[0].usage is not None
        assert changed[0].usage.model_dump(mode="json") == metadata["usage"]
        assert [item.job_id for item in await service.list_jobs("tenant-a")] == ["replacement"]
        assert [item.job_id for item in await service.list_jobs("tenant-a", archived=True)] == [
            "old"
        ]
        assert await asyncio.to_thread((tmp_path / "old.pdf").read_bytes) == original
        assert await asyncio.to_thread((tmp_path / "old.json").read_bytes) == artifact
        db.expire_all()
        persisted = await db.get(IngestionJob, "old")
        assert persisted is not None
        assert {
            key: value for key, value in persisted.meta.items() if key != "paper_archive"
        } == metadata
        assert persisted.status == IngestionStatus.COMPLETED
        assert persisted.created_at.replace(tzinfo=timezone.utc) == _NOW
        assert persisted.updated_at.replace(tzinfo=timezone.utc) == _NOW
        detail = await service.read_job("old", "tenant-a", include_result=True)
        assert detail is not None and detail.archived is True
        assert detail.result is not None and detail.result.document.document_id == _SOURCE_ID
        assert await service.find_job("old", "tenant-a") is not None
        assert len((await db.execute(select(Document))).scalars().all()) == 2


@pytest.mark.asyncio
async def test_archived_source_remains_resolvable_by_exact_document_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("UPLOADS_DIR", str(tmp_path))
    async with _database() as db:
        await _store(db, tmp_path, "only-source")
        service = PaperExtractionHistoryService(db)
        await service.set_archived(_request("only-source"), "tenant-a", user_id="reviewer")
        await db.commit()
        source = await service.read_by_document(_SOURCE_ID, "tenant-a")
        assert source is not None and source.job_id == "only-source" and source.archived
        assert source.result is not None
        assert source.result.document.text == "Exact retained source text"


@pytest.mark.asyncio
async def test_archive_preserves_approved_agreement_history_and_its_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("UPLOADS_DIR", str(tmp_path))
    async with _database() as db:
        await _store(db, tmp_path, "retained-source")
        master = SqlAlchemyAgreementRepository(db)
        identity = AgreementIdentity(vendor_id="vendor-1", store_id="store-1", contract_number="65")
        actor = AgreementActor(tenant_id="tenant-a", user_id="reviewer", can_approve=True)
        saved = await master.create(
            identity=identity,
            draft=AgreementDraft(
                terms=RentAgreementSchema(vendor_name="Reviewed Owner", contract_number="65"),
                effective_from=_NOW.date(),
                effective_to=_NOW.date(),
                source_document_ids=(_SOURCE_ID,),
                change_reason="Reviewed original source",
            ),
            actor=actor,
        )
        approved = await master.approve(
            agreement_id=saved.agreement_id,
            version_number=1,
            decision=ApprovalDecision(
                classification="psak73",
                rule_set_id="reviewed-policy",
                rule_set_version="1",
                reason="Approved exact snapshot",
            ),
            actor=actor,
        )
        await db.commit()
        before = approved.model_dump(mode="json")
        history = PaperExtractionHistoryService(db)
        await history.set_archived(_request("retained-source"), "tenant-a", user_id="reviewer")
        await db.commit()
        db.expire_all()
        reference = await master.find_approved(
            tenant_id="tenant-a", lookup=AgreementLookup(identity=identity, as_of=_NOW.date())
        )
        assert reference is not None and reference.model_dump(mode="json") == before
        source = await history.read_by_document(reference.draft.source_document_ids[0], "tenant-a")
        assert source is not None and source.archived and source.result is not None


@pytest.mark.asyncio
async def test_archive_restore_is_recoverable_idempotent_and_preserves_audit(
    tmp_path: Path,
) -> None:
    async with _database() as db:
        await _store(db, tmp_path, "old")
        service = PaperExtractionHistoryService(db)
        first = await service.set_archived(_request("old"), "tenant-a", user_id="reviewer")
        await db.commit()
        replay = await service.set_archived(_request("old"), "tenant-a", user_id="other-reviewer")
        assert replay[0].archived_at == first[0].archived_at
        assert replay[0].archived_by == "reviewer"
        restored = await service.set_archived(
            _request("old", archived=False), "tenant-a", user_id="restorer"
        )
        await db.commit()
        assert restored[0].archived is False
        assert restored[0].restored_by == "restorer" and restored[0].restored_at is not None
        assert restored[0].archived_by == "reviewer"
        assert restored[0].usage == first[0].usage
        assert [item.job_id for item in await service.list_jobs("tenant-a")] == ["old"]
        assert await service.list_jobs("tenant-a", archived=True) == ()


@pytest.mark.asyncio
async def test_historical_usage_remains_unknown_before_and_after_archive(tmp_path: Path) -> None:
    async with _database() as db:
        job = await _store(db, tmp_path, "historical")
        job.meta = {key: value for key, value in job.meta.items() if key != "usage"}
        await db.commit()
        service = PaperExtractionHistoryService(db)
        before = await service.read_job("historical", "tenant-a")
        assert before is not None and before.usage is None
        after = await service.set_archived(_request("historical"), "tenant-a", user_id="reviewer")
        assert after[0].usage is None


@pytest.mark.asyncio
async def test_reused_document_provenance_is_typed_and_survives_archive(tmp_path: Path) -> None:
    async with _database() as db:
        job = await _store(db, tmp_path, "reused")
        provenance = {
            "source_job_id": "verified-source",
            "source_sha256": "a" * 64,
            "mode": "retained_verified_ocr",
        }
        job.meta = {**job.meta, "document_reuse": provenance}
        await db.commit()
        history = PaperExtractionHistoryService(db)
        before = await history.read_job("reused", "tenant-a")
        assert before is not None and before.document_reuse is not None
        assert before.document_reuse.model_dump(mode="json") == provenance
        after = await history.set_archived(_request("reused"), "tenant-a", user_id="reviewer")
        assert after[0].document_reuse == before.document_reuse


@pytest.mark.asyncio
async def test_legacy_reuse_annotations_are_projected_without_rewriting_stored_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("UPLOADS_DIR", str(tmp_path))
    async with _database() as db:
        job = await _store(db, tmp_path, "legacy-reused")
        public_provenance = {
            "source_job_id": "verified-source",
            "source_sha256": "a" * 64,
            "mode": "retained_verified_ocr",
        }
        stored = {
            **job.meta,
            "document_reuse": {**public_provenance, "purpose": "historical private annotation"},
        }
        job.meta = stored
        await db.commit()
        await db.refresh(job)
        timestamps = job.created_at, job.updated_at
        history = PaperExtractionHistoryService(db)
        listed = await history.list_jobs("tenant-a")
        detail = await history.read_job("legacy-reused", "tenant-a")
        source = await history.read_by_document(_SOURCE_ID, "tenant-a")
        for projection in (listed[0], detail, source):
            assert projection is not None and projection.document_reuse is not None
            assert projection.document_reuse.model_dump(mode="json") == public_provenance
            assert "historical private annotation" not in projection.model_dump_json()
        await db.refresh(job)
        assert job.meta == stored
        assert (job.created_at, job.updated_at) == timestamps


@pytest.mark.parametrize(
    "provenance",
    [
        {"source_job_id": "../private", "source_sha256": "a" * 64, "mode": "retained_verified_ocr"},
        {"source_job_id": "source", "source_sha256": "bad", "mode": "retained_verified_ocr"},
        {"source_job_id": "source", "source_sha256": "a" * 64, "mode": "unverified"},
        {
            "source_job_id": "source",
            "source_sha256": "a" * 64,
            "mode": "retained_verified_ocr",
            "purpose": "legacy private annotation",
        },
    ],
)
def test_document_reuse_rejects_unsafe_or_unverified_provenance(
    provenance: dict[str, str],
) -> None:
    with pytest.raises(ValidationError):
        PaperExtractionJob.model_validate({**_job().model_dump(), "document_reuse": provenance})


@pytest.mark.parametrize("invalid", ["missing", "foreign", "legacy", "pending", "processing"])
@pytest.mark.asyncio
async def test_archive_rejects_mixed_invalid_batches_before_any_change(
    invalid: str, tmp_path: Path
) -> None:
    async with _database() as db:
        await _store(db, tmp_path, "valid")
        if invalid != "missing":
            await _store(
                db,
                tmp_path,
                invalid,
                tenant_id="tenant-b" if invalid == "foreign" else "tenant-a",
                workflow="legacy" if invalid == "legacy" else "paper_extraction",
                status={
                    "pending": IngestionStatus.PENDING,
                    "processing": IngestionStatus.PROCESSING,
                }.get(invalid, IngestionStatus.COMPLETED),
            )
        service = PaperExtractionHistoryService(db)
        with pytest.raises(PaperExtractionArchiveError) as caught:
            await service.set_archived(_request("valid", invalid), "tenant-a", user_id="reviewer")
        expected = "active_extraction" if invalid in {"pending", "processing"} else "not_found"
        assert caught.value.code == expected
        await db.commit()
        assert [item.job_id for item in await service.list_jobs("tenant-a") if item.archived] == []
        valid = await db.get(IngestionJob, "valid")
        assert valid is not None and "paper_archive" not in valid.meta


@pytest.mark.asyncio
async def test_service_leaves_transaction_ownership_to_caller(tmp_path: Path) -> None:
    async with _database() as db:
        await _store(db, tmp_path, "old")
        service = PaperExtractionHistoryService(db)
        await service.set_archived(_request("old"), "tenant-a", user_id="reviewer")
        await db.rollback()
        assert [item.job_id for item in await service.list_jobs("tenant-a")] == ["old"]
        assert await service.list_jobs("tenant-a", archived=True) == ()


def _job(*, archived: bool = False) -> PaperExtractionJob:
    return PaperExtractionJob(
        job_id="old",
        filename="contract.pdf",
        schema_name="rent_agreement",
        content_mode="text",
        status="completed",
        created_at=_NOW,
        updated_at=_NOW,
        archived=archived,
    )


def _app(history: object, db: object) -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_user_context] = lambda: UserContext(
        user_id="reviewer", tenant_id="tenant-a"
    )
    app.dependency_overrides[get_history_service] = lambda: history
    app.dependency_overrides[_db_session] = lambda: db
    return app


@pytest.mark.asyncio
async def test_archive_endpoint_uses_authenticated_scope_and_commits_after_validation() -> None:
    history, db = AsyncMock(), AsyncMock()
    history.set_archived.return_value = (_job(archived=True),)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=_app(history, db)), base_url="http://test"
    ) as client:
        response = await client.post(
            "/v1/paper/extractions/archive", json={"job_ids": ["old"], "archived": True}
        )
    assert response.status_code == 200, response.text
    assert response.json()[0]["archived"] is True
    history.set_archived.assert_awaited_once_with(_request("old"), "tenant-a", user_id="reviewer")
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_archived_original_file_and_page_preview_stay_available(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("UPLOADS_DIR", str(tmp_path))
    async with _database() as db:
        await _store(db, tmp_path, "old")
        history = PaperExtractionHistoryService(db)
        app = _app(history, db)
        preview = AsyncMock()
        preview.render.return_value = b"retained-preview"
        app.dependency_overrides[get_page_preview_service] = lambda: preview
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            archive = await client.post(
                "/v1/paper/extractions/archive", json={"job_ids": ["old"], "archived": True}
            )
            assert archive.status_code == 200
            active = await client.get("/v1/paper/extractions")
            original = await client.get("/v1/paper/extractions/old/file")
            page = await client.get("/v1/paper/extractions/old/pages/1")
        assert active.status_code == 200 and active.json() == []
        assert original.status_code == 200 and original.content == b"%PDF-1.7\noriginal"
        assert page.status_code == 200 and page.content == b"retained-preview"
        preview.render.assert_awaited_once_with((tmp_path / "old.pdf").resolve(), 1)


@pytest.mark.asyncio
async def test_archive_list_query_is_explicit_and_source_read_still_works() -> None:
    history, db = AsyncMock(), AsyncMock()
    history.list_jobs.return_value = (_job(archived=True),)
    history.read_job.return_value = _job(archived=True)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=_app(history, db)), base_url="http://test"
    ) as client:
        archived = await client.get("/v1/paper/extractions?archived=true&limit=10&offset=0")
        detail = await client.get("/v1/paper/extractions/old")
    assert archived.status_code == 200 and archived.json()[0]["archived"] is True
    assert detail.status_code == 200
    history.list_jobs.assert_awaited_once_with("tenant-a", limit=10, offset=0, archived=True)
    history.read_job.assert_awaited_once_with("old", "tenant-a", include_result=True)


@pytest.mark.parametrize("code, expected", [("not_found", 404), ("active_extraction", 409)])
@pytest.mark.asyncio
async def test_archive_endpoint_has_safe_atomic_errors(code: str, expected: int) -> None:
    history, db = AsyncMock(), AsyncMock()
    history.set_archived.side_effect = PaperExtractionArchiveError(code, "Safe failure.")
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=_app(history, db)), base_url="http://test"
    ) as client:
        response = await client.post(
            "/v1/paper/extractions/archive", json={"job_ids": ["old"], "archived": True}
        )
    assert response.status_code == expected
    assert response.json()["detail"]["code"] == code
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_archive_endpoint_rejects_injected_scope_without_echoing_values() -> None:
    history, db = AsyncMock(), AsyncMock()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=_app(history, db)), base_url="http://test"
    ) as client:
        response = await client.post(
            "/v1/paper/extractions/archive",
            json={"job_ids": ["old"], "archived": True, "tenant_id": "private-tenant"},
        )
    assert response.status_code == 422
    assert "private-tenant" not in response.text
    history.set_archived.assert_not_awaited()
    db.commit.assert_not_awaited()
