"""Uploaded originals transfer ownership only after a durable queue record exists."""

import asyncio
import threading
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy.exc import SQLAlchemyError

from src.api.auth import UserContext, get_user_context
from src.api.paper_extraction_routes import get_history_service, router
from src.db.models.ingestion import IngestionStatus


def application(history: SimpleNamespace) -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_user_context] = lambda: UserContext(
        user_id="u", tenant_id="tenant-a"
    )
    app.dependency_overrides[get_history_service] = lambda: history
    return app


def history_for_retry(source: Path) -> SimpleNamespace:
    return SimpleNamespace(
        find_job=AsyncMock(
            return_value=SimpleNamespace(
                id="original",
                file_path=str(source),
                status=IngestionStatus.FAILED,
                meta={
                    "workflow": "paper_extraction",
                    "schema_name": "rent_invoice",
                    "original_filename": "invoice.pdf",
                    "file_size": 8,
                },
            )
        ),
        read_job=AsyncMock(),
    )


async def post_source(client: httpx.AsyncClient, *, retry: bool) -> httpx.Response:
    if retry:
        return await client.post("/v1/paper/extractions/original/retry")
    return await client.post(
        "/v1/paper/extractions",
        files={"file": ("invoice.pdf", b"%PDF-1.7", "application/pdf")},
        data={"schema_name": "rent_invoice"},
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("retry", [False, True])
async def test_pre_persistence_failure_cleans_only_new_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, retry: bool
) -> None:
    monkeypatch.setenv("UPLOADS_DIR", str(tmp_path))
    original = tmp_path / "original.pdf"
    original.write_bytes(b"%PDF-1.7")
    history = history_for_retry(original)
    queue = SimpleNamespace(enqueue=AsyncMock(side_effect=RuntimeError("private failure")))
    with patch("src.api.paper_extraction_routes.get_ingestion_queue", return_value=queue):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=application(history), raise_app_exceptions=False),
            base_url="http://test",
        ) as client:
            response = await post_source(client, retry=retry)
    assert response.status_code == 503
    assert "private failure" not in response.text
    assert response.json()["detail"]["code"] == "queue_unavailable"
    assert list(tmp_path.iterdir()) == [original]
    assert original.read_bytes() == b"%PDF-1.7"


@pytest.mark.asyncio
@pytest.mark.parametrize("retry", [False, True])
async def test_persisted_publication_failure_keeps_source_for_history_retry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, retry: bool
) -> None:
    from src.ingestion.submission_error import QueueSubmissionError

    monkeypatch.setenv("UPLOADS_DIR", str(tmp_path))
    original = tmp_path / "original.pdf"
    original.write_bytes(b"%PDF-1.7")
    history = history_for_retry(original)
    queue = SimpleNamespace(enqueue=AsyncMock(side_effect=QueueSubmissionError("persisted-job")))
    with patch("src.api.paper_extraction_routes.get_ingestion_queue", return_value=queue):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=application(history), raise_app_exceptions=False),
            base_url="http://test",
        ) as client:
            response = await post_source(client, retry=retry)
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "queue_unavailable"
    queued_source = Path(queue.enqueue.call_args.args[0])
    assert queued_source != original
    assert queued_source.read_bytes() == b"%PDF-1.7"
    assert original.exists()


@pytest.mark.asyncio
@pytest.mark.parametrize("retry", [False, True])
async def test_history_read_failure_does_not_remove_a_successfully_queued_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, retry: bool
) -> None:
    monkeypatch.setenv("UPLOADS_DIR", str(tmp_path))
    original = tmp_path / "original.pdf"
    original.write_bytes(b"%PDF-1.7")
    history = history_for_retry(original)
    history.read_job.side_effect = SQLAlchemyError("private storage failure")
    queue = SimpleNamespace(enqueue=AsyncMock(return_value="persisted-job"))
    with patch("src.api.paper_extraction_routes.get_ingestion_queue", return_value=queue):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=application(history), raise_app_exceptions=False),
            base_url="http://test",
        ) as client:
            response = await post_source(client, retry=retry)
    assert response.status_code == 503
    assert "private storage failure" not in response.text
    queued_source = Path(queue.enqueue.call_args.args[0])
    assert queued_source.read_bytes() == b"%PDF-1.7"


@pytest.mark.asyncio
@pytest.mark.parametrize("persisted", [False, True])
async def test_cancelled_submission_preserves_only_durable_source_ownership(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, persisted: bool
) -> None:
    monkeypatch.setenv("UPLOADS_DIR", str(tmp_path))
    original = tmp_path / "original.pdf"
    original.write_bytes(b"%PDF-1.7")
    history = history_for_retry(original)
    if persisted:
        from src.ingestion.submission_cancelled_error import QueueSubmissionCancelledError

        error: BaseException = QueueSubmissionCancelledError("persisted-job")
    else:
        error = asyncio.CancelledError()
    queue = SimpleNamespace(enqueue=AsyncMock(side_effect=error))
    with patch("src.api.paper_extraction_routes.get_ingestion_queue", return_value=queue):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=application(history)), base_url="http://test"
        ) as client:
            with pytest.raises(asyncio.CancelledError):
                await post_source(client, retry=False)
    assert Path(queue.enqueue.call_args.args[0]).exists() is persisted
    assert original.exists()


@pytest.mark.asyncio
async def test_retry_copy_failure_removes_partial_copy_and_keeps_original(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("UPLOADS_DIR", str(tmp_path))
    original = tmp_path / "original.pdf"
    original.write_bytes(b"%PDF-1.7")
    history = history_for_retry(original)
    queue = SimpleNamespace(enqueue=AsyncMock())

    def failed_copy(source: Path, destination: Path) -> None:
        destination.write_bytes(b"partial")
        raise OSError("private storage details")

    with (
        patch("src.api.paper_extraction_routes.get_ingestion_queue", return_value=queue),
        patch("src.api.paper_extraction_routes.shutil.copyfile", side_effect=failed_copy),
    ):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=application(history)), base_url="http://test"
        ) as client:
            response = await post_source(client, retry=True)
    assert response.status_code == 503
    assert "private storage" not in response.text
    assert list(tmp_path.iterdir()) == [original]
    queue.enqueue.assert_not_awaited()


@pytest.mark.asyncio
async def test_cancelled_upload_waits_for_physical_write_before_removing_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from src.api import paper_extraction_routes as routes

    monkeypatch.setenv("UPLOADS_DIR", str(tmp_path))
    history = history_for_retry(tmp_path / "unused.pdf")
    queue = SimpleNamespace(enqueue=AsyncMock())
    started, release = threading.Event(), threading.Event()
    write = routes._write_upload

    def delayed_write(payload: bytes, root: Path) -> Path:
        started.set()
        if not release.wait(timeout=5):
            raise TimeoutError("Test write was not released")
        return write(payload, root)

    with (
        patch("src.api.paper_extraction_routes.get_ingestion_queue", return_value=queue),
        patch("src.api.paper_extraction_routes._write_upload", side_effect=delayed_write),
    ):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=application(history)), base_url="http://test"
        ) as client:
            request = asyncio.create_task(post_source(client, retry=False))
            assert await asyncio.to_thread(started.wait, 2)
            request.cancel()
            release.set()
            with pytest.raises(asyncio.CancelledError):
                await request
    assert not list(tmp_path.iterdir())
    queue.enqueue.assert_not_awaited()
