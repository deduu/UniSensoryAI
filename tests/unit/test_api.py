"""Tests for src/api/server.py — FastAPI endpoint tests."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport
from datetime import datetime, timezone

from src.db.session import get_db


@pytest.fixture
def mock_lifespan():
    """Override lifespan to skip DB/queue initialization in tests."""
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def noop_lifespan(app):
        yield

    return noop_lifespan


@pytest.fixture
def test_app(mock_lifespan):
    """Create a test FastAPI app with mocked lifespan and DB dependency override."""
    from src.api.server import app

    app.router.lifespan_context = mock_lifespan

    # Override the get_db dependency to avoid needing a real database
    mock_session = AsyncMock()

    async def override_get_db():
        return mock_session

    app.dependency_overrides[get_db] = override_get_db

    yield app

    # Cleanup
    app.dependency_overrides.clear()


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


@pytest.mark.asyncio
async def test_get_job_status_found(test_app):
    """GET /v1/jobs/{id} should return job details when found."""
    mock_job = MagicMock()
    mock_job.id = "found-job-id"
    mock_job.status.value = "COMPLETED"
    mock_job.created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    mock_job.updated_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    mock_job.file_path = "/uploads/test.pdf"
    mock_job.meta = {"model_id": "qwen2-vl-2b-instruct"}
    mock_job.documents = []

    mock_service = MagicMock()
    mock_service.get_by_id = AsyncMock(return_value=mock_job)

    with patch("src.api.server.IngestionService", return_value=mock_service):
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/v1/jobs/found-job-id")

    assert response.status_code == 200
    data = response.json()
    assert data["job_id"] == "found-job-id"
    assert data["status"] == "COMPLETED"


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
