"""Stored uploads remain accessible when switching between Windows and Docker."""

import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.upload_storage import get_upload_directory, resolve_upload_path


def test_upload_directory_honors_settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("UPLOADS_DIR", str(tmp_path))
    assert get_upload_directory() == tmp_path
    monkeypatch.delenv("UPLOADS_DIR")
    assert get_upload_directory() == Path("data/uploads")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "stored",
    [
        r"C:\Users\developer\UniSensoryAI\data\uploads\retained.pdf",
        "/app/data/uploads/retained.pdf",
        "data/uploads/retained.pdf",
        "retained.pdf",
    ],
)
async def test_legacy_host_and_container_paths_resolve_without_rewriting_records(
    stored: str, tmp_path: Path
) -> None:
    upload = tmp_path / "retained.pdf"
    upload.write_bytes(b"retained document")
    assert await resolve_upload_path(stored, upload_dir=tmp_path) == upload.resolve()


@pytest.mark.asyncio
async def test_native_upload_path_still_resolves(tmp_path: Path) -> None:
    upload = tmp_path / "manual.pdf"
    upload.write_bytes(b"manual document")
    assert await resolve_upload_path(str(upload), upload_dir=tmp_path) == upload.resolve()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "stored",
    [
        r"C:\private\retained.pdf",
        "/etc/retained.pdf",
        "/app/data/uploads/../retained.pdf",
        "../retained.pdf",
        "/app/data/uploads/missing.pdf",
    ],
)
async def test_missing_or_unrelated_paths_cannot_select_an_upload_by_filename(
    stored: str, tmp_path: Path
) -> None:
    (tmp_path / "retained.pdf").write_bytes(b"retained document")
    with pytest.raises(FileNotFoundError):
        await resolve_upload_path(stored, upload_dir=tmp_path)


@pytest.mark.asyncio
async def test_existing_file_outside_upload_directory_is_rejected(tmp_path: Path) -> None:
    uploads = tmp_path / "uploads"
    uploads.mkdir()
    outside = tmp_path / "outside.pdf"
    outside.write_bytes(b"unrelated file")
    with pytest.raises(FileNotFoundError):
        await resolve_upload_path(str(outside), upload_dir=uploads)


@pytest.mark.asyncio
async def test_memory_worker_retries_a_retained_windows_upload(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from src.ingestion import queue_manager

    upload = tmp_path / "retained.pdf"
    upload.write_bytes(b"retained document")
    monkeypatch.setenv("UPLOADS_DIR", str(tmp_path))
    job = SimpleNamespace(
        file_path=r"C:\old-workspace\data\uploads\retained.pdf",
        tenant_id="tenant-1",
        meta={"model_id": "gpt-4o", "original_filename": "retained.pdf"},
    )
    session = AsyncMock()
    manager = MagicMock()
    manager.session.return_value.__aenter__ = AsyncMock(return_value=session)
    manager.session.return_value.__aexit__ = AsyncMock(return_value=False)
    monkeypatch.setattr(queue_manager.db_session, "session_manager", manager)
    service = MagicMock()
    service.update_status = AsyncMock(return_value=job)
    service.mark_completed = AsyncMock()
    service.mark_failed = AsyncMock()
    monkeypatch.setattr(queue_manager, "IngestionService", lambda _: service)
    documents = MagicMock()
    documents.create_document = AsyncMock()
    monkeypatch.setattr(queue_manager, "DocumentService", lambda _: documents)
    processor = AsyncMock(return_value={"content": "retained document"})
    queue = queue_manager.IngestionQueue(processor)
    await queue.queue.put("retained-job")
    await queue.start_worker()
    try:
        await asyncio.wait_for(queue.queue.join(), timeout=3)
    finally:
        await queue.stop_worker()
    processor.assert_awaited_once_with(str(upload.resolve()), "gpt-4o")
    service.mark_completed.assert_awaited_once()
    service.mark_failed.assert_not_awaited()


@pytest.mark.asyncio
async def test_redis_worker_retries_a_retained_windows_upload(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from src.ingestion import redis_queue

    upload = tmp_path / "retained.pdf"
    upload.write_bytes(b"retained document")
    monkeypatch.setenv("UPLOADS_DIR", str(tmp_path))
    job = SimpleNamespace(
        file_path=r"C:\old-workspace\data\uploads\retained.pdf",
        tenant_id="tenant-1",
        meta={"model_id": "gpt-4o"},
    )
    session = AsyncMock()
    manager = MagicMock()
    manager.session.return_value.__aenter__ = AsyncMock(return_value=session)
    manager.session.return_value.__aexit__ = AsyncMock(return_value=False)
    monkeypatch.setattr(redis_queue.db_session, "session_manager", manager)
    service = MagicMock()
    service.update_status = AsyncMock(return_value=job)
    service.mark_completed = AsyncMock()
    monkeypatch.setattr(redis_queue, "IngestionService", lambda _: service)
    documents = MagicMock()
    documents.create_document = AsyncMock()
    monkeypatch.setattr(redis_queue, "DocumentService", lambda _: documents)
    processor = AsyncMock(return_value={"content": "retained document"})
    queue = redis_queue.RedisIngestionQueue(processor)
    queue._get_redis = AsyncMock(return_value=AsyncMock())
    await queue._process_job("retained-job", worker_id=0)
    processor.assert_awaited_once_with(str(upload.resolve()), "gpt-4o")
    service.mark_completed.assert_awaited_once()
