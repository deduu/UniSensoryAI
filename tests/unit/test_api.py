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
from unittest.mock import AsyncMock, MagicMock, patch

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
    "fitz", "pymupdf", "pymupdf.extra", "pymupdf._extra",
]
for mod in _MOCK_MODULES:
    if mod not in sys.modules:
        sys.modules[mod] = MagicMock()

from httpx import AsyncClient, ASGITransport  # noqa: E402
from src.db.session import get_db  # noqa: E402
from src.db.models.ingestion import IngestionStatus  # noqa: E402
from src.policy.models import PolicyReviewResult  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

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
    from src.api.auth import get_current_user

    app.router.lifespan_context = mock_lifespan

    mock_session = AsyncMock()

    async def override_get_db():
        return mock_session

    async def override_auth():
        return {"sub": "test-user"}

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_auth

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
async def test_preview_job_file_as_text_for_docx(test_app):
    """Office source preview should return extracted text instead of forcing inline DOCX."""
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
        patch("src.api.server.Path.exists", return_value=True),
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
    mock_service.list_jobs.assert_called_once_with(limit=10, offset=5)


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

    with patch("src.api.server.IngestionService", return_value=mock_service):
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
    mock_queue.queue = MagicMock()
    mock_queue.queue.put = AsyncMock()

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
    mock_queue.queue.put.assert_called_once_with("retry-job")


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
