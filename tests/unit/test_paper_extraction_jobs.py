"""Queued PAPER extraction preserves source output independently of business fields."""

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi import FastAPI
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from src.api.auth import UserContext, get_user_context
from src.api.paper_extraction_routes import get_history_service, router
from src.db.base import Base
from src.db.models.document import Document
from src.db.models.ingestion import IngestionJob, IngestionStatus
from src.db.models.tenant import Tenant
from src.extraction.contracts import (
    DocumentResult,
    ExtractionIssue,
    ExtractionOptions,
    FieldExtractionResult,
    ImageAsset,
    PageContent,
    TextBlock,
)
from src.extraction.errors import ExtractionError
from src.ingestion.queue_manager import IngestionQueue
from src.ingestion.redis_queue import RedisIngestionQueue
from src.ingestion.submission_error import QueueSubmissionError
from src.paper.extraction_contracts import PaperExtractionResult
from src.services.paper_extraction import PaperExtractionProcessor
from src.services.paper_extraction_history import PaperExtractionHistoryService


def document() -> DocumentResult:
    return DocumentResult(
        document_id="source-sha256",
        source_name="invoice.pdf",
        content_mode="text",
        text="Invoice INV-123",
        pages=(
            PageContent(
                page_number=1,
                width=400,
                height=500,
                text_blocks=(TextBlock(block_id="p1-text", page_number=1, text="Invoice INV-123"),),
            ),
        ),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("timeout_seconds", [300.0, 1800.0])
async def test_processor_options_preserve_deployment_budget_and_copy_content_mode(
    timeout_seconds: float, tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("UPLOADS_DIR", str(tmp_path))
    source = tmp_path / "source.pdf"
    source.write_bytes(b"%PDF-1.7")
    service = SimpleNamespace(
        extract_document=AsyncMock(return_value=document()),
        extract_fields=AsyncMock(
            return_value=FieldExtractionResult(
                schema_id="paper.rent_invoice", schema_version="1", data={}
            )
        ),
    )
    template = ExtractionOptions(
        timeout_seconds=timeout_seconds,
        content_mode="multimodal",
        max_pages=75,
        fields_profile="custom-fields",
    )
    processor = PaperExtractionProcessor(AsyncMock(return_value=service), options=template)
    await processor.process(
        str(source),
        {
            "workflow": "paper_extraction",
            "schema_name": "rent_invoice",
            "content_mode": "text",
            "original_filename": "invoice.pdf",
            "file_size": 8,
        },
    )
    used = service.extract_document.call_args.args[1]
    assert used.timeout_seconds == timeout_seconds
    assert used.max_pages == 75
    assert used.text_strategy == "native_then_ocr"
    assert used.content_mode == "text"
    assert template.content_mode == "multimodal"
    assert service.extract_fields.call_args.kwargs == {
        "model_profile": "custom-fields",
        "timeout_seconds": timeout_seconds,
    }


def test_processor_revalidates_injected_options() -> None:
    invalid = ExtractionOptions().model_copy(update={"timeout_seconds": 0})
    with pytest.raises(ValidationError):
        PaperExtractionProcessor(AsyncMock(), options=invalid)


@pytest.mark.asyncio
async def test_document_failure_logs_only_safe_error_code(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("UPLOADS_DIR", str(tmp_path))
    source = tmp_path / "source.pdf"
    source.write_bytes(b"%PDF-1.7")
    service = SimpleNamespace(
        extract_document=AsyncMock(
            side_effect=ExtractionError("timeout", "Private provider response")
        )
    )
    with patch("src.services.paper_extraction.logger") as logger:
        with pytest.raises(ExtractionError) as error:
            await PaperExtractionProcessor(AsyncMock(return_value=service)).process(
                str(source),
                {
                    "workflow": "paper_extraction",
                    "schema_name": "rent_invoice",
                    "content_mode": "text",
                    "original_filename": "invoice.pdf",
                    "file_size": 8,
                },
            )
        logger.warning.assert_called_once_with(
            "paper_document_extraction_failed", error_code="timeout"
        )
    assert "Private" not in str(error.value)


@pytest.mark.asyncio
async def test_fields_failure_keeps_full_document_and_safe_warning(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("UPLOADS_DIR", str(tmp_path))
    source = tmp_path / "source.pdf"
    source.write_bytes(b"%PDF-1.7")
    service = SimpleNamespace(
        extract_document=AsyncMock(return_value=document()),
        extract_fields=AsyncMock(side_effect=ExtractionError("schema_validation_failed", "secret")),
    )
    processor = PaperExtractionProcessor(AsyncMock(return_value=service))
    output = await processor.process(
        str(source),
        {
            "workflow": "paper_extraction",
            "schema_name": "rent_invoice",
            "content_mode": "text",
            "original_filename": "invoice.pdf",
            "file_size": 8,
        },
    )
    assert output["content"] == "Invoice INV-123"
    assert "secret" not in str(output)
    assert output["job_metadata"]["extraction_status"] == "partial"
    artifact = tmp_path / output["chunks"][0]["artifact_name"]
    result = PaperExtractionResult.model_validate_json(artifact.read_text())
    assert result.fields is None
    assert result.document.document_id == "source-sha256"
    assert result.document.pages[0].text_blocks[0].block_id == "p1-text"
    assert result.warnings[0].code == "schema_validation_failed"
    assert result.status == "partial"
    options = service.extract_document.call_args.args[1]
    assert options.text_strategy == "native_then_ocr"
    assert options.timeout_seconds == 300.0


@pytest.mark.asyncio
async def test_fields_success_persists_evidence_without_heavy_job_metadata(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("UPLOADS_DIR", str(tmp_path))
    source = tmp_path / "source.pdf"
    source.write_bytes(b"%PDF-1.7")
    fields = FieldExtractionResult(
        schema_id="paper.rent_invoice",
        schema_version="1",
        data={"invoice_number": "INV-123"},
        evidence=(
            {"field_path": "/invoice_number", "source_ids": ["p1-text"], "quote": "INV-123"},
        ),
    )
    service = SimpleNamespace(
        extract_document=AsyncMock(return_value=document()),
        extract_fields=AsyncMock(return_value=fields),
    )
    output = await PaperExtractionProcessor(AsyncMock(return_value=service)).process(
        str(source),
        {
            "workflow": "paper_extraction",
            "schema_name": "rent_invoice",
            "content_mode": "text",
            "original_filename": "invoice.pdf",
            "file_size": 8,
        },
    )
    assert "INV-123" not in str(output["job_metadata"])
    assert output["job_metadata"]["document_id"] == document().document_id
    assert "data_base64" not in str(output["chunks"])
    artifact = tmp_path / output["chunks"][0]["artifact_name"]
    restored = PaperExtractionResult.model_validate_json(artifact.read_text())
    assert restored.fields.evidence == fields.evidence
    assert restored.status == "succeeded"


@pytest.mark.asyncio
@pytest.mark.parametrize("backend", ["memory", "redis"])
async def test_workflow_dispatch_keeps_legacy_processor_separate(
    backend: str, tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("UPLOADS_DIR", str(tmp_path))
    (tmp_path / "source.pdf").write_bytes(b"%PDF-1.7")
    legacy = AsyncMock(return_value={"content": "legacy"})
    handler = AsyncMock(
        return_value={"content": "paper", "chunks": [], "job_metadata": {"page_count": 1}}
    )
    job = SimpleNamespace(
        id="job-1",
        file_path="source.pdf",
        tenant_id="tenant-a",
        meta={"workflow": "paper_extraction"},
    )
    with patch("src.db.session.session_manager") as manager:
        session = AsyncMock()
        manager.session.return_value.__aenter__.return_value = session
        module = (
            "src.ingestion.queue_manager" if backend == "memory" else "src.ingestion.redis_queue"
        )
        with (
            patch(f"{module}.IngestionService") as jobs,
            patch(f"{module}.DocumentService") as documents,
        ):
            jobs.return_value.update_status = AsyncMock(return_value=job)
            jobs.return_value.mark_completed = AsyncMock()
            documents.return_value.create_document = AsyncMock()
            if backend == "memory":
                queue = IngestionQueue(legacy, workflow_handlers={"paper_extraction": handler})
                await queue.queue.put("job-1")
                await queue.start_worker()
                await __import__("asyncio").wait_for(queue.queue.join(), timeout=2)
                await queue.stop_worker()
            else:
                queue = RedisIngestionQueue(legacy, workflow_handlers={"paper_extraction": handler})
                queue._redis = AsyncMock()
                await queue._process_job("job-1", worker_id=0)
            handler.assert_awaited_once()
            legacy.assert_not_awaited()
            assert jobs.return_value.mark_completed.call_args.args[1] == {"page_count": 1}


@pytest.mark.asyncio
async def test_history_survives_service_recreation_and_is_tenant_scoped(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("UPLOADS_DIR", str(tmp_path))
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", poolclass=StaticPool)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as db:
        db.add_all(
            [Tenant(id="tenant-a", name="A", slug="a"), Tenant(id="tenant-b", name="B", slug="b")]
        )
        for identity, tenant, workflow in (
            ("own", "tenant-a", "paper_extraction"),
            ("other", "tenant-b", "paper_extraction"),
            ("legacy", "tenant-a", "legacy"),
        ):
            db.add(
                IngestionJob(
                    id=identity,
                    tenant_id=tenant,
                    file_path="source.pdf",
                    status=IngestionStatus.PENDING,
                    meta={
                        "workflow": workflow,
                        "schema_name": "rent_invoice",
                        "content_mode": "text",
                        "original_filename": "invoice.pdf",
                        "file_size": 8,
                    },
                )
            )
        await db.commit()
    async with maker() as db:
        history = PaperExtractionHistoryService(db)
        assert [item.job_id for item in await history.list_jobs("tenant-a")] == ["own"]
        assert await history.find_job("other", "tenant-a") is None
        assert await history.find_job("legacy", "tenant-a") is None
    await engine.dispose()


@pytest.mark.asyncio
async def test_upload_queues_without_inference_and_sanitizes_filename(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("UPLOADS_DIR", str(tmp_path))
    application = FastAPI()
    application.include_router(router)
    application.dependency_overrides[get_user_context] = lambda: UserContext(
        user_id="u", tenant_id="tenant-a"
    )
    history = MagicMock()
    now = datetime.now(timezone.utc)
    history.read_job = AsyncMock(
        return_value={
            "job_id": "job-1",
            "filename": "invoice.pdf",
            "schema_name": "rent_invoice",
            "content_mode": "text",
            "status": "pending",
            "created_at": now,
            "updated_at": now,
            "warning_count": 0,
        }
    )
    application.dependency_overrides[get_history_service] = lambda: history
    queue = SimpleNamespace(enqueue=AsyncMock(return_value="job-1"))
    with patch("src.api.paper_extraction_routes.get_ingestion_queue", return_value=queue):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=application), base_url="http://test"
        ) as client:
            response = await client.post(
                "/v1/paper/extractions",
                files={"file": ("../../invoice.pdf", b"%PDF-1.7", "application/pdf")},
                data={"schema_name": "rent_invoice"},
            )
    assert response.status_code == 202, response.text
    args = queue.enqueue.call_args
    assert args.kwargs["tenant_id"] == "tenant-a"
    assert args.kwargs["meta"]["original_filename"] == "invoice.pdf"
    assert Path(args.args[0]).parent == tmp_path
    assert "api_keys" not in args.kwargs["meta"]


@pytest.mark.asyncio
async def test_invalid_pdf_never_enqueues(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("UPLOADS_DIR", str(tmp_path))
    application = FastAPI()
    application.include_router(router)
    application.dependency_overrides[get_user_context] = lambda: UserContext(
        user_id="u", tenant_id="tenant-a"
    )
    application.dependency_overrides[get_history_service] = lambda: MagicMock()
    queue = SimpleNamespace(enqueue=AsyncMock())
    with patch("src.api.paper_extraction_routes.get_ingestion_queue", return_value=queue):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=application), base_url="http://test"
        ) as client:
            response = await client.post(
                "/v1/paper/extractions",
                files={"file": ("invoice.pdf", b"not a PDF", "application/pdf")},
                data={"schema_name": "rent_invoice"},
            )
    assert response.status_code == 422
    queue.enqueue.assert_not_awaited()
    assert not list(tmp_path.iterdir())


@pytest.mark.asyncio
@pytest.mark.parametrize("backend", ["memory", "redis"])
async def test_requeue_reuses_job_id_without_creating_record(backend: str) -> None:
    processor = AsyncMock()
    if backend == "memory":
        queue = IngestionQueue(processor)
        await queue.requeue("existing-job")
        assert queue.queue.get_nowait() == "existing-job"
    else:
        queue = RedisIngestionQueue(processor)
        queue._redis = AsyncMock()
        await queue.requeue("existing-job")
        queue._redis.rpush.assert_awaited_once_with(queue.queue_key, "existing-job")
    processor.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("backend", ["memory", "redis"])
async def test_unknown_workflow_does_not_fall_back_to_legacy(
    backend: str, tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("UPLOADS_DIR", str(tmp_path))
    (tmp_path / "source.pdf").write_bytes(b"%PDF-1.7")
    legacy = AsyncMock()
    job = SimpleNamespace(
        id="job-1", file_path="source.pdf", tenant_id="tenant-a", meta={"workflow": "unknown"}
    )
    with patch("src.db.session.session_manager") as manager:
        manager.session.return_value.__aenter__.return_value = AsyncMock()
        module = (
            "src.ingestion.queue_manager" if backend == "memory" else "src.ingestion.redis_queue"
        )
        with patch(f"{module}.IngestionService") as jobs:
            jobs.return_value.update_status = AsyncMock(return_value=job)
            jobs.return_value.mark_failed = AsyncMock()
            if backend == "memory":
                queue = IngestionQueue(legacy)
                await queue.queue.put("job-1")
                await queue.start_worker()
                await __import__("asyncio").wait_for(queue.queue.join(), timeout=2)
                await queue.stop_worker()
                jobs.return_value.mark_failed.assert_awaited_once_with(
                    "job-1", "Queued workflow is unavailable."
                )
            else:
                queue = RedisIngestionQueue(legacy)
                queue._handle_failure = AsyncMock()
                await queue._process_job("job-1", worker_id=0)
                queue._handle_failure.assert_awaited_once_with(
                    "job-1", "Queued workflow is unavailable.", workflow="unknown"
                )
    legacy.assert_not_awaited()


@pytest.mark.asyncio
async def test_reopen_result_after_new_session_and_block_cross_tenant_file(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("UPLOADS_DIR", str(tmp_path))
    source = tmp_path / "source.pdf"
    source.write_bytes(b"%PDF-1.7")
    fields = FieldExtractionResult(
        schema_id="paper.rent_invoice", schema_version="1", data={"invoice_number": "INV-123"}
    )
    extraction = SimpleNamespace(
        extract_document=AsyncMock(return_value=document()),
        extract_fields=AsyncMock(return_value=fields),
    )
    output = await PaperExtractionProcessor(AsyncMock(return_value=extraction)).process(
        str(source),
        {
            "workflow": "paper_extraction",
            "schema_name": "rent_invoice",
            "content_mode": "text",
            "original_filename": "invoice.pdf",
            "file_size": 8,
        },
    )
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", poolclass=StaticPool)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as db:
        db.add(Tenant(id="tenant-a", name="A", slug="a"))
        db.add(
            IngestionJob(
                id="own",
                tenant_id="tenant-a",
                file_path=str(source),
                status=IngestionStatus.COMPLETED,
                meta={
                    "workflow": "paper_extraction",
                    "schema_name": "rent_invoice",
                    "content_mode": "text",
                    "original_filename": "invoice.pdf",
                    "file_size": 8,
                    **output["job_metadata"],
                },
            )
        )
        db.add(
            Document(
                id="doc-db-id",
                tenant_id="tenant-a",
                job_id="own",
                filename="invoice.pdf",
                content_text=output["content"],
                content_chunks=output["chunks"],
            )
        )
        await db.commit()
    async with maker() as db:
        history = PaperExtractionHistoryService(db)
        restored = await history.read_job("own", "tenant-a", include_result=True)
        assert restored.result.document.document_id == "source-sha256"
        assert restored.result.document.text == "Invoice INV-123"
        assert restored.result.fields.data == fields.data
        application = FastAPI()
        application.include_router(router)
        application.dependency_overrides[get_user_context] = lambda: UserContext(
            user_id="u", tenant_id="tenant-b"
        )
        application.dependency_overrides[get_history_service] = lambda: history
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=application), base_url="http://test"
        ) as client:
            for suffix in ("", "/file"):
                response = await client.get("/v1/paper/extractions/own" + suffix)
                assert response.status_code == 404
        application.dependency_overrides[get_user_context] = lambda: UserContext(
            user_id="u", tenant_id="tenant-a"
        )
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=application), base_url="http://test"
        ) as client:
            response = await client.get("/v1/paper/extractions/own/file")
            assert response.status_code == 200
            assert response.content == b"%PDF-1.7"
    await engine.dispose()


@pytest.mark.asyncio
async def test_retry_keeps_old_history_and_copies_original_source(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("UPLOADS_DIR", str(tmp_path))
    source = tmp_path / "source.pdf"
    source.write_bytes(b"%PDF-1.7")
    now = datetime.now(timezone.utc)
    original = SimpleNamespace(
        id="failed",
        file_path=str(source),
        status=IngestionStatus.FAILED,
        meta={
            "workflow": "paper_extraction",
            "schema_name": "rent_invoice",
            "content_mode": "text",
            "original_filename": "invoice.pdf",
            "file_size": 8,
        },
    )
    history = SimpleNamespace(
        find_job=AsyncMock(return_value=original),
        read_job=AsyncMock(
            return_value={
                "job_id": "new",
                "filename": "invoice.pdf",
                "schema_name": "rent_invoice",
                "content_mode": "text",
                "status": "pending",
                "created_at": now,
                "updated_at": now,
            }
        ),
    )
    application = FastAPI()
    application.include_router(router)
    application.dependency_overrides[get_user_context] = lambda: UserContext(
        user_id="u", tenant_id="tenant-a"
    )
    application.dependency_overrides[get_history_service] = lambda: history
    queue = SimpleNamespace(enqueue=AsyncMock(return_value="new"))
    with patch("src.api.paper_extraction_routes.get_ingestion_queue", return_value=queue):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=application), base_url="http://test"
        ) as client:
            response = await client.post("/v1/paper/extractions/failed/retry")
    assert response.status_code == 202
    copied = Path(queue.enqueue.call_args.args[0])
    assert copied != source
    assert copied.read_bytes() == source.read_bytes()
    assert queue.enqueue.call_args.kwargs["meta"]["retry_of"] == "failed"
    assert original.status == IngestionStatus.FAILED


@pytest.mark.asyncio
async def test_upload_worker_and_fresh_app_reopen_complete_persisted_result(
    tmp_path: Path, monkeypatch
) -> None:
    """Exercise HTTP, the real queue, DB/artifact storage, and a fresh app read."""
    import asyncio

    monkeypatch.setenv("UPLOADS_DIR", str(tmp_path))
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", poolclass=StaticPool)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as db:
        db.add(Tenant(id="tenant-a", name="A", slug="a"))
        await db.commit()

    @asynccontextmanager
    async def host_session():
        async with maker() as db:
            yield db

    extracted = document().model_copy(
        update={
            "model_ids": ("vision-model",),
            "content_mode": "multimodal",
            "pages": (
                document()
                .pages[0]
                .model_copy(
                    update={
                        "images": (
                            ImageAsset(
                                asset_id="page-image-1", page_number=1, data_base64="cGFnZQ=="
                            ),
                        )
                    }
                ),
            ),
            "warnings": (ExtractionIssue(code="ocr_review", message="Review OCR quality."),),
        }
    )
    fields = FieldExtractionResult(
        schema_id="paper.rent_invoice",
        schema_version="1",
        model_ids=("fields-model",),
        data={"invoice_number": "INV-123"},
        evidence=(
            {"field_path": "/invoice_number", "source_ids": ["p1-text"], "quote": "INV-123"},
        ),
        warnings=(
            ExtractionIssue(code="optional_missing", message="Review missing optional fields."),
        ),
    )
    extraction = SimpleNamespace(
        extract_document=AsyncMock(return_value=extracted),
        extract_fields=AsyncMock(return_value=fields),
    )
    processor = PaperExtractionProcessor(AsyncMock(return_value=extraction))
    queue = IngestionQueue(AsyncMock(), workflow_handlers={"paper_extraction": processor.process})
    monkeypatch.setattr("src.db.session.session_manager", SimpleNamespace(session=host_session))

    async def history_dependency():
        async with maker() as db:
            yield PaperExtractionHistoryService(db)

    def new_app() -> FastAPI:
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_user_context] = lambda: UserContext(
            user_id="u", tenant_id="tenant-a"
        )
        app.dependency_overrides[get_history_service] = history_dependency
        return app

    with patch("src.api.paper_extraction_routes.get_ingestion_queue", return_value=queue):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=new_app()), base_url="http://test"
        ) as client:
            uploaded = await client.post(
                "/v1/paper/extractions",
                files={"file": ("invoice.pdf", b"%PDF-1.7", "application/pdf")},
                data={"schema_name": "rent_invoice", "content_mode": "multimodal"},
            )
            assert uploaded.status_code == 202, uploaded.text
            job_id = uploaded.json()["job_id"]
        await queue.start_worker()
        await asyncio.wait_for(queue.queue.join(), timeout=5)
        await queue.stop_worker()
        # A fresh app and fresh DB dependency cannot rely on in-memory UI state.
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=new_app()), base_url="http://test"
        ) as client:
            listing = (await client.get("/v1/paper/extractions")).json()
            assert len(listing) == 1
            assert listing[0]["status"] == "completed"
            assert listing[0]["warning_count"] == 2
            assert listing[0]["model_ids"] == ["vision-model", "fields-model"]
            assert listing[0]["model_usage_recorded"] is True
            assert listing[0]["file_size"] == len(b"%PDF-1.7")
            assert "data_base64" not in str(listing)
            assert "INV-123" not in str(listing)
            detail = (await client.get(f"/v1/paper/extractions/{job_id}")).json()
            assert detail["model_ids"] == listing[0]["model_ids"]
            result = PaperExtractionResult.model_validate(detail["result"])
            assert result.document == extracted
            assert result.fields == fields
            assert result.status == "partial"
            assert (await client.get(f"/v1/paper/extractions/{job_id}/file")).content == b"%PDF-1.7"
    await engine.dispose()


@pytest.mark.asyncio
async def test_workflow_retry_status_is_pending_until_attempts_exhausted() -> None:
    queue = RedisIngestionQueue(AsyncMock())
    queue._redis = AsyncMock()
    queue._redis.incr.return_value = 1
    with (
        patch("src.db.session.session_manager") as manager,
        patch("src.ingestion.redis_queue.IngestionService") as jobs,
        patch("src.ingestion.redis_queue.asyncio.sleep", new_callable=AsyncMock),
    ):
        manager.session.return_value.__aenter__.return_value = AsyncMock()
        jobs.return_value.update_status = AsyncMock()
        jobs.return_value.mark_failed = AsyncMock()
        await queue._handle_failure("job-1", "Safe failure", workflow="paper_extraction")
        jobs.return_value.update_status.assert_awaited_once_with(
            "job-1", IngestionStatus.PENDING, {"retry_count": 1}
        )
        jobs.return_value.mark_failed.assert_not_awaited()


@pytest.mark.asyncio
async def test_redis_enqueue_failure_marks_paper_job_failed_for_history() -> None:
    queue = RedisIngestionQueue(AsyncMock())
    queue._redis = AsyncMock()
    queue._redis.rpush.side_effect = ConnectionError("private backend connection")
    with (
        patch("src.db.session.session_manager") as manager,
        patch("src.ingestion.redis_queue.IngestionService") as jobs,
    ):
        manager.session.return_value.__aenter__.return_value = AsyncMock()
        jobs.return_value.create_job = AsyncMock(return_value=SimpleNamespace(id="job-1"))
        jobs.return_value.mark_failed = AsyncMock()
        with pytest.raises(QueueSubmissionError):
            await queue.enqueue(
                "source.pdf", meta={"workflow": "paper_extraction"}, tenant_id="tenant-a"
            )
        jobs.return_value.mark_failed.assert_awaited_once_with(
            "job-1", "The job could not be queued. Retry the stored upload."
        )
