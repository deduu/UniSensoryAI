"""Tests for src/api/server.py — FastAPI endpoint tests.

Covers ALL endpoints:
  GET  /              — health check
  GET  /health        — health check (alias)
  POST /v1/process_document — upload
  GET  /v1/jobs       — list jobs
  GET  /v1/jobs/{id}  — get job
  DELETE /v1/jobs/{id} — delete job
  POST /v1/jobs/{id}/retry — retry failed job
"""

import sys
from pathlib import Path
from typing import Any, Awaitable, Callable
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
import pytest
from datetime import datetime, timezone
from contextlib import asynccontextmanager

# ---------------------------------------------------------------------------
# Mock heavy ML modules before importing anything from src.models
# This prevents ImportError for torch/transformers/etc. in CI/test envs.
# ---------------------------------------------------------------------------
_MOCK_MODULES = [
    "torch", "torch.cuda", "torch.nn", "torch.nn.functional",
    "torchvision", "torchvision.transforms",
    "transformers", "accelerate", "bitsandbytes",
    "nvitop",
]
for mod in _MOCK_MODULES:
    if mod not in sys.modules:
        sys.modules[mod] = MagicMock()

from httpx import AsyncClient, ASGITransport  # noqa: E402
from src.db.session import get_db  # noqa: E402
from src.db.models.ingestion import IngestionStatus  # noqa: E402
from src.policy.models import PolicyReviewResult  # noqa: E402


def test_openapi_schema_includes_paper_routes_and_html_preview(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Swagger includes business review routes and advertises the HTML preview."""
    from src.api.server import app

    monkeypatch.setattr(app, "openapi_schema", None)
    schema = app.openapi()
    paths = schema["paths"]
    assert "/v1/paper/agreements" in paths
    assert "get" in paths["/v1/paper/agreements"]
    assert "/v1/paper/review-context" in paths
    assert "/v1/paper/agreements/{agreement_id}/versions/{version_number}/approval" in paths
    assert "/v1/paper/cases" in paths
    assert "/v1/paper/cases/{case_id}/versions/{version_number}/decision" in paths
    assert "post" in paths["/v1/paper/extractions"]
    assert "get" in paths["/v1/paper/extractions"]
    assert "get" in paths["/v1/paper/extractions/{job_id}"]
    assert "get" in paths["/v1/paper/extractions/{job_id}/file"]
    response = paths["/v1/jobs/{job_id}/preview/html"]["get"]["responses"]["200"]
    assert "text/html" in response["content"]


@pytest.mark.asyncio
@pytest.mark.parametrize("owned", [True, False])
async def test_extraction_lifespan_retains_host_resource_ownership(
    monkeypatch: pytest.MonkeyPatch, owned: bool
) -> None:
    from fastapi import FastAPI
    from src.api import server

    application = FastAPI()
    application.state.extraction_service = AsyncMock()
    application.state.extraction_service_owned = owned
    service = application.state.extraction_service
    queue = AsyncMock()
    monkeypatch.setattr(server, "init_db", lambda url: None)
    monkeypatch.setattr(server.db_session, "session_manager", None)
    monkeypatch.setattr(server, "init_ingestion_queue", lambda processor, **kwargs: queue)
    async with server.lifespan(application):
        pass
    queue.stop_worker.assert_awaited_once()
    if owned:
        service.aclose.assert_awaited_once()
    else:
        service.aclose.assert_not_awaited()


@pytest.mark.asyncio
async def test_extraction_lifespan_cleans_up_when_application_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from fastapi import FastAPI
    from src.api import server

    application = FastAPI()
    service, queue = AsyncMock(), AsyncMock()
    application.state.extraction_service = service
    application.state.extraction_service_owned = True
    monkeypatch.setattr(server, "init_db", lambda url: None)
    monkeypatch.setattr(server.db_session, "session_manager", None)
    monkeypatch.setattr(server, "init_ingestion_queue", lambda processor, **kwargs: queue)
    with pytest.raises(RuntimeError, match="application failure"):
        async with server.lifespan(application):
            raise RuntimeError("application failure")
    queue.stop_worker.assert_awaited_once()
    service.aclose.assert_awaited_once()


@pytest.mark.asyncio
async def test_lifespan_registers_paper_workflow_and_reuses_application_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Queued extraction resolves the same app runtime lazily, without startup inference."""
    from src.api import server

    application = FastAPI()
    service, queue = AsyncMock(), AsyncMock()
    captured: dict[str, Any] = {}

    class Processor:
        def __init__(self, service_factory: Callable[[], Awaitable[Any]], **kwargs: Any) -> None:
            captured["factory"] = service_factory
            captured.update(kwargs)

        async def process(self, file_path: str, metadata: dict[str, Any]) -> dict[str, Any]:
            return {}

    def queue_factory(processor: Any, **kwargs: Any) -> AsyncMock:
        captured.update(kwargs)
        return queue

    factory = AsyncMock(return_value=service)
    monkeypatch.setenv("EXTRACTION_WORKFLOW_TIMEOUT_SECONDS", "540")
    monkeypatch.setattr(server, "init_db", lambda url: None)
    monkeypatch.setattr(server.db_session, "session_manager", None)
    monkeypatch.setattr(server, "init_ingestion_queue", queue_factory)
    monkeypatch.setattr(server, "PaperExtractionProcessor", Processor, raising=False)
    monkeypatch.setattr(server, "get_extraction_service", factory, raising=False)
    async with server.lifespan(application):
        factory.assert_not_awaited()
        assert captured["options"].timeout_seconds == 540
        assert callable(captured["workflow_handlers"]["paper_extraction"])
        assert await captured["factory"]() is service
        assert factory.call_args.args[0].app is application
    queue.stop_worker.assert_awaited_once()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("backend", ["memory", "redis"])
async def test_startup_recovery_respects_durable_queue(
    monkeypatch: pytest.MonkeyPatch, backend: str
) -> None:
    """Starting an API must not fail jobs retained by a Redis worker queue."""
    from src.api import server

    manager, session, service, queue = MagicMock(), AsyncMock(), MagicMock(), AsyncMock()
    manager.session.return_value.__aenter__.return_value = session
    service.fail_interrupted_jobs = AsyncMock(return_value=0)
    monkeypatch.setenv("QUEUE_BACKEND", backend)
    monkeypatch.setattr(server, "init_db", lambda url: None)
    monkeypatch.setattr(server.db_session, "session_manager", manager)
    monkeypatch.setattr(server, "IngestionService", lambda db: service)
    monkeypatch.setattr(server, "init_ingestion_queue", lambda processor, **kwargs: queue)
    async with server.lifespan(FastAPI()):
        pass
    assert service.fail_interrupted_jobs.await_count == (1 if backend == "memory" else 0)


@pytest.mark.asyncio
@pytest.mark.parametrize("endpoint", ["/v1/jobs", "/v1/jobs/private-job"])
async def test_job_history_never_serializes_provider_credentials(
    test_app: FastAPI, endpoint: str
) -> None:
    """Workers retain credentials, while history only receives safe metadata."""
    metadata = {
        "model_id": "generic-model",
        "api_keys": {"cloud": "private-sentinel"},
        "api_key": "private-single-sentinel",
        "original_filename": "invoice.pdf",
    }
    job = _make_mock_job(job_id="private-job", meta=metadata)
    service = MagicMock()
    service.list_jobs = AsyncMock(return_value=[job])
    service.get_by_id = AsyncMock(return_value=job)
    with patch("src.api.server.IngestionService", return_value=service):
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            response = await client.get(endpoint)
    assert response.status_code == 200
    data = response.json()[0] if endpoint == "/v1/jobs" else response.json()
    assert data["meta"] == {"model_id": "generic-model", "original_filename": "invoice.pdf"}
    assert "private-sentinel" not in response.text
    assert job.meta == metadata


@pytest.mark.asyncio
@pytest.mark.parametrize("commit_fails", [False, True])
async def test_delete_paper_job_cleans_owned_artifact_only_after_commit(
    test_app: FastAPI, tmp_path: Path, commit_fails: bool
) -> None:
    """Database rollback preserves files, and typed tenant ownership limits cleanup."""
    import uuid
    from src.api import server

    source = tmp_path / "source.pdf"
    owned = tmp_path / f"{uuid.uuid4()}.paper-extraction.json"
    foreign = tmp_path / f"{uuid.uuid4()}.paper-extraction.json"
    unrelated = tmp_path / "unrelated.json"
    for path in (source, owned, foreign, unrelated):
        path.write_text("test-only")
    doc, other_doc = _make_mock_doc(), _make_mock_doc()
    doc.tenant_id, other_doc.tenant_id = "default", "other"
    doc.content_chunks = [
        {"type": "paper_extraction_artifact", "version": "1", "artifact_name": owned.name},
        {"type": "paper_extraction_artifact", "version": "1", "artifact_name": unrelated.name},
        {"type": "paper_extraction_artifact", "version": "1", "artifact_name": "../outside.json"},
    ]
    other_doc.content_chunks = [
        {"type": "paper_extraction_artifact", "version": "1", "artifact_name": foreign.name}
    ]
    job = _make_mock_job(file_path=str(source), documents=[doc, other_doc])
    service, session = MagicMock(), AsyncMock()
    service.get_by_id = AsyncMock(return_value=job)
    service.delete = AsyncMock()
    if commit_fails:
        session.commit.side_effect = RuntimeError("test database unavailable")

    async def database() -> AsyncMock:
        return session

    server.app.dependency_overrides[get_db] = database
    with (
        patch.object(server, "IngestionService", return_value=service),
        patch.object(server, "UPLOAD_DIR", tmp_path),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            response = await client.delete("/v1/jobs/test-job-id")
    assert response.status_code == (500 if commit_fails else 200)
    assert source.exists() is commit_fails
    assert owned.exists() is commit_fails
    assert foreign.exists()
    assert unrelated.exists()


@pytest.fixture
def mock_lifespan():
    """Override lifespan to skip DB/queue initialization in tests."""

    @asynccontextmanager
    async def noop_lifespan(app):
        yield

    return noop_lifespan


@pytest.fixture
def test_app(mock_lifespan):
    """Create a test FastAPI app with mocked lifespan and DB dependency override."""
    from src.api.server import app
    from src.api.auth import get_user_context, UserContext

    app.router.lifespan_context = mock_lifespan

    mock_session = AsyncMock()

    async def override_get_db():
        return mock_session

    async def override_user_context():
        return UserContext(user_id="test-user", tenant_id="default", email=None)

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_user_context] = override_user_context

    yield app

    app.dependency_overrides.clear()


def _make_mock_job(
    job_id="test-job-id",
    status=IngestionStatus.COMPLETED,
    file_path="/uploads/test.pdf",
    meta=None,
    documents=None,
):
    """Helper to create a mock IngestionJob."""
    job = MagicMock()
    job.id = job_id
    job.status = status  # Real enum — job.status.value works naturally
    job.created_at = datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
    job.updated_at = datetime(2026, 1, 15, 12, 5, 0, tzinfo=timezone.utc)
    job.file_path = file_path
    job.meta = meta or {"model_id": "qwen2-vl-2b-instruct"}
    job.documents = documents or []
    return job


def _make_mock_doc(doc_id="doc-1", filename="test.pdf", content_text="Extracted text"):
    """Helper to create a mock Document."""
    doc = MagicMock()
    doc.id = doc_id
    doc.filename = filename
    doc.content_text = content_text
    return doc


# ---------------------------------------------------------------------------
# GET / — Health check
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_health_check(test_app):
    """GET / should return 200 with healthy status."""
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "UniSensoryAI"


@pytest.mark.asyncio
async def test_health_check_alias(test_app):
    """GET /health should also return 200 with healthy status."""
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


# ---------------------------------------------------------------------------
# POST /v1/process_document — Upload
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_process_document_upload(test_app, tmp_path):
    """POST /v1/process_document should return 202 with job_id."""
    mock_queue = MagicMock()
    mock_queue.enqueue = AsyncMock(return_value="test-job-id")

    with (
        patch("src.api.server.get_ingestion_queue", return_value=mock_queue),
        patch("src.api.server.UPLOAD_DIR", tmp_path),
    ):
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/v1/process_document",
                files={"file": ("test.pdf", b"%PDF-1.4 test content", "application/pdf")},
                data={"model_id": "qwen2-vl-2b-instruct"},
            )

    assert response.status_code == 202
    data = response.json()
    assert data["job_id"] == "test-job-id"
    assert data["status"] == "queued"
    assert "message" in data


@pytest.mark.asyncio
async def test_process_document_upload_default_model(test_app, tmp_path):
    """POST /v1/process_document without model_id uses default."""
    mock_queue = MagicMock()
    mock_queue.enqueue = AsyncMock(return_value="job-default-model")

    with (
        patch("src.api.server.get_ingestion_queue", return_value=mock_queue),
        patch("src.api.server.UPLOAD_DIR", tmp_path),
    ):
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/v1/process_document",
                files={"file": ("doc.pdf", b"%PDF-1.4 content", "application/pdf")},
            )

    assert response.status_code == 202
    # enqueue should have been called with the default model_id
    mock_queue.enqueue.assert_called_once()
    call_kwargs = mock_queue.enqueue.call_args
    assert call_kwargs[1]["meta"]["model_id"] == "qwen3-vl-30b"


@pytest.mark.asyncio
async def test_process_document_upload_no_file(test_app):
    """POST /v1/process_document without file should return 422."""
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/v1/process_document")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_process_document_upload_queue_error(test_app, tmp_path):
    """POST /v1/process_document should return 500 when queue fails."""
    mock_queue = MagicMock()
    mock_queue.enqueue = AsyncMock(side_effect=RuntimeError("Queue broken"))

    with (
        patch("src.api.server.get_ingestion_queue", return_value=mock_queue),
        patch("src.api.server.UPLOAD_DIR", tmp_path),
    ):
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/v1/process_document",
                files={"file": ("test.pdf", b"%PDF-1.4 content", "application/pdf")},
            )

    assert response.status_code == 500


# ---------------------------------------------------------------------------
# GET /v1/jobs — List jobs
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_preview_job_file_as_text_for_docx(test_app, tmp_path):
    """Office source preview should return extracted text instead of forcing inline DOCX."""
    (tmp_path / "proposed-policy.docx").write_bytes(b"document source")
    mock_job = _make_mock_job(
        job_id="job-docx",
        file_path="/uploads/proposed-policy.docx",
        meta={"original_filename": "proposed-policy.docx"},
    )
    mock_service = MagicMock()
    mock_service.get_by_id = AsyncMock(return_value=mock_job)

    with (
        patch("src.api.server.IngestionService", return_value=mock_service),
        patch("src.api.server.DocumentConverter.convert", return_value=["Full policy text"]),
        patch("src.api.server.UPLOAD_DIR", tmp_path),
    ):
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/v1/jobs/job-docx/preview")

    assert response.status_code == 200
    assert response.json() == {
        "filename": "proposed-policy.docx",
        "content_type": "text/plain",
        "content": "Full policy text",
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("suffix", ["file", "preview", "preview/html"])
async def test_existing_windows_upload_remains_accessible(
    test_app: FastAPI, tmp_path: Path, suffix: str
) -> None:
    """Mounted uploads remain downloadable and previewable after a Docker switch."""
    upload = tmp_path / "retained.docx"
    upload.write_bytes(b"retained document")
    job = _make_mock_job(
        file_path=r"C:\old-workspace\data\uploads\retained.docx",
        meta={"original_filename": "retained.docx"},
    )
    service = MagicMock()
    service.get_by_id = AsyncMock(return_value=job)
    with (
        patch("src.api.server.IngestionService", return_value=service),
        patch("src.api.server.UPLOAD_DIR", tmp_path),
        patch("src.api.server.DocumentConverter.convert", return_value=["retained preview"]),
        patch("src.api.server.DocumentConverter.to_html", return_value="<p>retained preview</p>"),
    ):
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(f"/v1/jobs/retained-job/{suffix}")
    assert response.status_code == 200
    if suffix == "file":
        assert response.content == b"retained document"
    elif suffix == "preview":
        assert response.json()["content"] == "retained preview"
    else:
        assert response.text == "<p>retained preview</p>"


@pytest.mark.asyncio
async def test_delete_existing_windows_upload_uses_mounted_copy(
    test_app: FastAPI, tmp_path: Path
) -> None:
    upload = tmp_path / "retained.pdf"
    upload.write_bytes(b"retained document")
    job = _make_mock_job(file_path=r"C:\old-workspace\data\uploads\retained.pdf")
    service = MagicMock()
    service.get_by_id = AsyncMock(return_value=job)
    service.delete = AsyncMock()
    with (
        patch("src.api.server.IngestionService", return_value=service),
        patch("src.api.server.UPLOAD_DIR", tmp_path),
    ):
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.delete("/v1/jobs/retained-job")
    assert response.status_code == 200
    assert not upload.exists()


@pytest.mark.asyncio
async def test_list_jobs_empty(test_app):
    """GET /v1/jobs should return empty list when no jobs exist."""
    mock_service = MagicMock()
    mock_service.list_jobs = AsyncMock(return_value=[])

    with patch("src.api.server.IngestionService", return_value=mock_service):
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/v1/jobs")

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_list_jobs_with_results(test_app):
    """GET /v1/jobs should return job list with documents."""
    doc = _make_mock_doc()
    job = _make_mock_job(documents=[doc])
    mock_service = MagicMock()
    mock_service.list_jobs = AsyncMock(return_value=[job])

    with patch("src.api.server.IngestionService", return_value=mock_service):
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/v1/jobs")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["job_id"] == "test-job-id"
    assert data[0]["status"] == "COMPLETED"
    assert len(data[0]["documents"]) == 1
    assert data[0]["documents"][0]["id"] == "doc-1"


@pytest.mark.asyncio
async def test_list_jobs_pagination(test_app):
    """GET /v1/jobs with limit and offset should pass them to service."""
    mock_service = MagicMock()
    mock_service.list_jobs = AsyncMock(return_value=[])

    with patch("src.api.server.IngestionService", return_value=mock_service):
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/v1/jobs?limit=10&offset=5")

    assert response.status_code == 200
    mock_service.list_jobs.assert_called_once_with(
        limit=10, offset=5, tenant_id="default"
    )


@pytest.mark.asyncio
async def test_list_jobs_invalid_limit(test_app):
    """GET /v1/jobs with limit=0 should return 422 (ge=1)."""
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/v1/jobs?limit=0")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_list_jobs_returns_full_content_text(test_app):
    """GET /v1/jobs should return full content_text for document views."""
    long_text = "A" * 600
    doc = _make_mock_doc(content_text=long_text)
    job = _make_mock_job(documents=[doc])
    mock_service = MagicMock()
    mock_service.list_jobs = AsyncMock(return_value=[job])

    with patch("src.api.server.IngestionService", return_value=mock_service):
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/v1/jobs")

    data = response.json()
    content = data[0]["documents"][0]["content_text"]
    assert content == long_text


# ---------------------------------------------------------------------------
# GET /v1/jobs/{job_id} — Get single job
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_job_status_found(test_app):
    """GET /v1/jobs/{id} should return job details when found."""
    job = _make_mock_job(job_id="found-job-id")
    mock_service = MagicMock()
    mock_service.get_by_id = AsyncMock(return_value=job)

    with patch("src.api.server.IngestionService", return_value=mock_service):
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/v1/jobs/found-job-id")

    assert response.status_code == 200
    data = response.json()
    assert data["job_id"] == "found-job-id"
    assert data["status"] == "COMPLETED"
    assert "created_at" in data
    assert "updated_at" in data
    assert "meta" in data


@pytest.mark.asyncio
async def test_get_job_status_not_found(test_app):
    """GET /v1/jobs/{id} should return 404 when job not found."""
    mock_service = MagicMock()
    mock_service.get_by_id = AsyncMock(return_value=None)

    with patch("src.api.server.IngestionService", return_value=mock_service):
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/v1/jobs/nonexistent-id")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_job_with_documents(test_app):
    """GET /v1/jobs/{id} should include document details."""
    doc = _make_mock_doc(doc_id="doc-abc", filename="report.pdf", content_text="Hello world")
    job = _make_mock_job(job_id="job-with-docs", documents=[doc])
    mock_service = MagicMock()
    mock_service.get_by_id = AsyncMock(return_value=job)

    with patch("src.api.server.IngestionService", return_value=mock_service):
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/v1/jobs/job-with-docs")

    assert response.status_code == 200
    data = response.json()
    assert len(data["documents"]) == 1
    assert data["documents"][0]["id"] == "doc-abc"
    assert data["documents"][0]["filename"] == "report.pdf"
    # Single-job endpoint returns full content_text (no truncation)
    assert data["documents"][0]["content_text"] == "Hello world"


# ---------------------------------------------------------------------------
# DELETE /v1/jobs/{job_id} — Delete job
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_delete_job_success(test_app, tmp_path):
    """DELETE /v1/jobs/{id} should delete job and uploaded file."""
    # Create a temp file to simulate the upload
    upload_file = tmp_path / "uploaded.pdf"
    upload_file.write_bytes(b"fake pdf")

    job = _make_mock_job(job_id="del-job", file_path=str(upload_file))
    mock_service = MagicMock()
    mock_service.get_by_id = AsyncMock(return_value=job)
    mock_service.delete = AsyncMock()

    mock_session = AsyncMock()

    async def override_get_db():
        return mock_session

    from src.api.server import app
    app.dependency_overrides[get_db] = override_get_db

    with (
        patch("src.api.server.IngestionService", return_value=mock_service),
        patch("src.api.server.UPLOAD_DIR", tmp_path),
    ):
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.delete("/v1/jobs/del-job")

    assert response.status_code == 200
    assert response.json()["detail"] == "Job deleted"
    mock_service.delete.assert_called_once_with("del-job")
    # File should have been cleaned up
    assert not upload_file.exists()


@pytest.mark.asyncio
async def test_delete_job_not_found(test_app):
    """DELETE /v1/jobs/{id} should return 404 when job not found."""
    mock_service = MagicMock()
    mock_service.get_by_id = AsyncMock(return_value=None)

    with patch("src.api.server.IngestionService", return_value=mock_service):
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.delete("/v1/jobs/no-such-job")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_job_missing_file(test_app):
    """DELETE /v1/jobs/{id} should succeed even if uploaded file is already gone."""
    job = _make_mock_job(job_id="del-job-2", file_path="/nonexistent/path/file.pdf")
    mock_service = MagicMock()
    mock_service.get_by_id = AsyncMock(return_value=job)
    mock_service.delete = AsyncMock()

    mock_session = AsyncMock()

    async def override_get_db():
        return mock_session

    from src.api.server import app
    app.dependency_overrides[get_db] = override_get_db

    with patch("src.api.server.IngestionService", return_value=mock_service):
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.delete("/v1/jobs/del-job-2")

    assert response.status_code == 200
    assert response.json()["detail"] == "Job deleted"


# ---------------------------------------------------------------------------
# POST /v1/jobs/{job_id}/retry — Retry failed job
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_retry_failed_job(test_app):
    """POST /v1/jobs/{id}/retry should re-enqueue a FAILED job."""
    job = _make_mock_job(
        job_id="retry-job",
        status=IngestionStatus.FAILED,
        meta={"model_id": "qwen2-vl-2b-instruct", "error": "OOM"},
    )
    mock_service = MagicMock()
    mock_service.get_by_id = AsyncMock(return_value=job)
    mock_service.update_status = AsyncMock()

    mock_queue = MagicMock()
    mock_queue.requeue = AsyncMock()

    mock_session = AsyncMock()

    async def override_get_db():
        return mock_session

    from src.api.server import app
    app.dependency_overrides[get_db] = override_get_db

    with (
        patch("src.api.server.IngestionService", return_value=mock_service),
        patch("src.api.server.get_ingestion_queue", return_value=mock_queue),
    ):
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/v1/jobs/retry-job/retry")

    assert response.status_code == 200
    data = response.json()
    assert data["job_id"] == "retry-job"
    assert data["status"] == "PENDING"
    assert "re-queued" in data["message"].lower()

    # Should have updated status and re-enqueued
    mock_service.update_status.assert_called_once()
    mock_queue.requeue.assert_awaited_once_with("retry-job")


@pytest.mark.asyncio
async def test_retry_non_failed_job(test_app):
    """POST /v1/jobs/{id}/retry should return 400 for non-FAILED jobs."""
    job = _make_mock_job(job_id="ok-job", status=IngestionStatus.COMPLETED)
    mock_service = MagicMock()
    mock_service.get_by_id = AsyncMock(return_value=job)

    with patch("src.api.server.IngestionService", return_value=mock_service):
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/v1/jobs/ok-job/retry")

    assert response.status_code == 400
    assert "failed" in response.json()["detail"].lower() or "COMPLETED" in response.json()["detail"]


@pytest.mark.asyncio
async def test_retry_job_not_found(test_app):
    """POST /v1/jobs/{id}/retry should return 404 for missing job."""
    mock_service = MagicMock()
    mock_service.get_by_id = AsyncMock(return_value=None)

    with patch("src.api.server.IngestionService", return_value=mock_service):
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/v1/jobs/ghost-id/retry")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_retry_pending_job(test_app):
    """POST /v1/jobs/{id}/retry should return 400 for PENDING jobs."""
    job = _make_mock_job(job_id="pending-job", status=IngestionStatus.PENDING)
    mock_service = MagicMock()
    mock_service.get_by_id = AsyncMock(return_value=job)

    with patch("src.api.server.IngestionService", return_value=mock_service):
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/v1/jobs/pending-job/retry")

    assert response.status_code == 400


# ---------------------------------------------------------------------------
# POST /v1/jobs/{job_id}/policy-review — Parallel policy review
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_review_job_policy_success(test_app):
    """POST /v1/jobs/{id}/policy-review should return orchestrated findings."""
    mock_service = MagicMock()
    mock_service.review_job = AsyncMock(
        return_value=PolicyReviewResult(
            job_id="policy-job",
            document_id="doc-1",
            filename="policy.pdf",
            summary="No contradictions or interference risks were detected by the configured agents.",
        )
    )

    with patch("src.api.server.PolicyReviewService", return_value=mock_service):
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/v1/jobs/policy-job/policy-review",
                json={"include_database": True, "include_web_search": False},
            )

    assert response.status_code == 200
    data = response.json()
    assert data["job_id"] == "policy-job"
    assert data["document_id"] == "doc-1"
    assert data["findings"] == []
    mock_service.review_job.assert_called_once()


@pytest.mark.asyncio
async def test_get_job_policy_review_returns_saved_result(test_app):
    """GET /v1/jobs/{id}/policy-review should return a saved review result."""
    mock_service = MagicMock()
    mock_service.get_saved_review = AsyncMock(
        return_value=PolicyReviewResult(
            job_id="policy-job",
            document_id="doc-1",
            filename="policy.pdf",
            summary="Saved policy review",
        )
    )

    with patch("src.api.server.PolicyReviewService", return_value=mock_service):
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/v1/jobs/policy-job/policy-review")

    assert response.status_code == 200
    data = response.json()
    assert data["summary"] == "Saved policy review"
    mock_service.get_saved_review.assert_called_once_with("policy-job")


@pytest.mark.asyncio
async def test_get_job_policy_review_returns_404_when_missing(test_app):
    """GET /v1/jobs/{id}/policy-review should be 404 when no review has been saved."""
    mock_service = MagicMock()
    mock_service.get_saved_review = AsyncMock(return_value=None)

    with patch("src.api.server.PolicyReviewService", return_value=mock_service):
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/v1/jobs/policy-job/policy-review")

    assert response.status_code == 404
    assert "No saved policy review" in response.json()["detail"]


@pytest.mark.asyncio
async def test_review_job_policy_rejects_unreviewable_job(test_app):
    """POST /v1/jobs/{id}/policy-review should return 400 for non-completed jobs."""
    mock_service = MagicMock()
    mock_service.review_job = AsyncMock(side_effect=ValueError("Only completed jobs can be reviewed."))

    with patch("src.api.server.PolicyReviewService", return_value=mock_service):
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/v1/jobs/pending-job/policy-review",
                json={"include_database": True},
            )

    assert response.status_code == 400
    assert "completed" in response.json()["detail"]
