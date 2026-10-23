"""Resolve canonical source identities without filenames or cross-tenant artifacts."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from src.api.auth import UserContext, get_user_context
from src.api.paper_extraction_routes import get_history_service, router
from src.db.base import Base
from src.db.models.document import Document
from src.db.models.ingestion import IngestionJob, IngestionStatus
from src.db.models.tenant import Tenant
from src.extraction.contracts import DocumentResult, PageContent
from src.paper.extraction_contracts import PaperExtractionJob, PaperExtractionResult
from src.services.paper_extraction_history import PaperExtractionHistoryService
from src.services.upload_storage import resolve_upload_path

SOURCE_ID = "a" * 64
OTHER_ID = "b" * 64
NOW = datetime(2026, 10, 17, tzinfo=timezone.utc)


def _result(document_id: str) -> PaperExtractionResult:
    return PaperExtractionResult(
        document=DocumentResult(
            document_id=document_id,
            source_name="same-name.pdf",
            content_mode="text",
            text="Retained original content",
            pages=(PageContent(page_number=1, width=100, height=100),),
        )
    )


@asynccontextmanager
async def _database() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", poolclass=StaticPool)
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
    source_id: str,
    *,
    age: int = 0,
    tenant_id: str = "tenant-a",
    indexed_id: str | None = None,
    corrupt: bool = False,
) -> None:
    artifact_name = f"{job_id}.paper-extraction.json"
    payload = "invalid private artifact" if corrupt else _result(source_id).model_dump_json()
    await asyncio.to_thread((root / artifact_name).write_text, payload, encoding="utf-8")
    db.add(
        IngestionJob(
            id=job_id,
            tenant_id=tenant_id,
            file_path="original.pdf",
            status=IngestionStatus.COMPLETED,
            created_at=NOW - timedelta(minutes=age),
            updated_at=NOW,
            meta={
                "workflow": "paper_extraction",
                "schema_name": "rent_invoice",
                "original_filename": "same-name.pdf",
                **({"document_id": indexed_id} if indexed_id else {}),
            },
        )
    )
    db.add(
        Document(
            id=f"db-{job_id}",
            tenant_id=tenant_id,
            job_id=job_id,
            filename="same-name.pdf",
            content_chunks=[{"type": "paper_extraction_artifact", "artifact_name": artifact_name}],
        )
    )
    await db.commit()


@pytest.mark.asyncio
async def test_lookup_returns_newest_verified_result_including_legacy_jobs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("UPLOADS_DIR", str(tmp_path))
    async with _database() as db:
        await _store(db, tmp_path, "older-indexed", SOURCE_ID, age=4, indexed_id=SOURCE_ID)
        await _store(db, tmp_path, "legacy-match", SOURCE_ID, age=3)
        await _store(db, tmp_path, "same-filename", OTHER_ID, age=2)
        await _store(db, tmp_path, "wrong-metadata", OTHER_ID, age=1, indexed_id=SOURCE_ID)
        await _store(db, tmp_path, "foreign-newest", SOURCE_ID, tenant_id="tenant-b")
        found = await PaperExtractionHistoryService(db).read_by_document(SOURCE_ID, "tenant-a")
        assert found is not None
        assert found.job_id == "legacy-match"
        assert found.result is not None
        assert found.result.document.document_id == SOURCE_ID


@pytest.mark.asyncio
async def test_lookup_scans_legacy_history_in_pages_and_never_uses_filename(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("UPLOADS_DIR", str(tmp_path))
    async with _database() as db:
        await _store(db, tmp_path, "old-match", SOURCE_ID, age=100)
        for index in range(55):
            await _store(db, tmp_path, f"unrelated-{index}", OTHER_ID, age=index)
        history = PaperExtractionHistoryService(db)
        found = await history.read_by_document(SOURCE_ID, "tenant-a")
        assert found is not None and found.job_id == "old-match"
        assert await history.read_by_document("c" * 64, "tenant-a") is None
        assert await history.read_by_document(SOURCE_ID, "tenant-b") is None


@pytest.mark.asyncio
async def test_lookup_skips_unreadable_artifacts_and_unrelated_indexed_results(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("UPLOADS_DIR", str(tmp_path))
    async with _database() as db:
        await _store(db, tmp_path, "valid", SOURCE_ID, age=5, indexed_id=SOURCE_ID)
        await _store(db, tmp_path, "corrupt", SOURCE_ID, age=3, corrupt=True)
        await _store(db, tmp_path, "unrelated-index", OTHER_ID, indexed_id=OTHER_ID)
        with patch(
            "src.services.paper_extraction_history.resolve_upload_path",
            wraps=resolve_upload_path,
        ) as resolve:
            found = await PaperExtractionHistoryService(db).read_by_document(SOURCE_ID, "tenant-a")
        assert found is not None and found.job_id == "valid"
        assert "unrelated-index.paper-extraction.json" not in [
            call.args[0] for call in resolve.await_args_list
        ]


@pytest.mark.asyncio
async def test_lookup_does_not_follow_foreign_document_or_oversized_missing_artifacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("UPLOADS_DIR", str(tmp_path))
    monkeypatch.setattr("src.services.paper_extraction_history._MAX_ARTIFACT_BYTES", 32)
    async with _database() as db:
        await _store(db, tmp_path, "oversized", SOURCE_ID, age=3)
        await _store(db, tmp_path, "missing", SOURCE_ID, age=2)
        await asyncio.to_thread((tmp_path / "missing.paper-extraction.json").unlink)
        await _store(db, tmp_path, "foreign-document", SOURCE_ID)
        foreign = await db.get(Document, "db-foreign-document")
        assert foreign is not None
        foreign.tenant_id = "tenant-b"
        await db.commit()
        with patch(
            "src.services.paper_extraction_history.resolve_upload_path", wraps=resolve_upload_path
        ) as resolve:
            found = await PaperExtractionHistoryService(db).read_by_document(SOURCE_ID, "tenant-a")
            assert found is None
        assert "foreign-document.paper-extraction.json" not in [
            call.args[0] for call in resolve.await_args_list
        ]


def _app(history: object) -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_user_context] = lambda: UserContext(
        user_id="reviewer", tenant_id="tenant-a"
    )
    app.dependency_overrides[get_history_service] = lambda: history
    return app


@pytest.mark.asyncio
async def test_source_lookup_route_returns_result_and_uses_authenticated_tenant() -> None:
    job = PaperExtractionJob(
        job_id="stored-job",
        filename="same-name.pdf",
        schema_name="rent_invoice",
        content_mode="text",
        status="completed",
        created_at=NOW,
        updated_at=NOW,
        result=_result(SOURCE_ID),
    )
    history = AsyncMock()
    history.read_by_document.return_value = job
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=_app(history)), base_url="http://test"
    ) as client:
        response = await client.get(f"/v1/paper/extractions/by-document/{SOURCE_ID}")
    assert response.status_code == 200, response.text
    assert response.json()["result"]["document"]["document_id"] == SOURCE_ID
    history.read_by_document.assert_awaited_once_with(SOURCE_ID, "tenant-a")


@pytest.mark.asyncio
@pytest.mark.parametrize("document_id", ["x" * 129, "private%20document", "bad%3Fidentifier"])
async def test_source_lookup_route_rejects_invalid_identity_without_echoing_it(
    document_id: str,
) -> None:
    history = AsyncMock()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=_app(history)), base_url="http://test"
    ) as client:
        response = await client.get(f"/v1/paper/extractions/by-document/{document_id}")
    assert response.status_code == 422
    assert "identifier" not in response.text and "private" not in response.text
    history.read_by_document.assert_not_awaited()


@pytest.mark.asyncio
async def test_source_lookup_route_has_sanitized_missing_and_storage_errors() -> None:
    history = AsyncMock()
    history.read_by_document.return_value = None
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=_app(history)), base_url="http://test"
    ) as client:
        missing = await client.get(f"/v1/paper/extractions/by-document/{SOURCE_ID}")
        assert missing.status_code == 404
        assert missing.json()["detail"]["code"] == "not_found"
        history.read_by_document.side_effect = OSError("private storage path")
        unavailable = await client.get(f"/v1/paper/extractions/by-document/{SOURCE_ID}")
        assert unavailable.status_code == 503
        assert "private" not in unavailable.text
