"""PAPER worker ownership, post-commit housekeeping, and graceful interruption checks."""

import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from src.db.models.ingestion import IngestionStatus
from src.extraction.contracts import DocumentResult, FieldExtractionResult
from src.ingestion.queue_manager import IngestionQueue
from src.ingestion.redis_queue import RedisIngestionQueue
from src.ingestion.submission_cancelled_error import QueueSubmissionCancelledError
from src.ingestion.submission_error import QueueSubmissionError
from src.ingestion.workflow_recovery import recover_interrupted_workflow
from src.services.paper_extraction import PaperExtractionProcessor


async def _owned_output(tmp_path: Path) -> dict:
    source = tmp_path / "source.pdf"
    source.write_bytes(b"%PDF-1.7")
    service = SimpleNamespace(
        extract_document=AsyncMock(
            return_value=DocumentResult(
                document_id="hash",
                source_name="invoice.pdf",
                content_mode="text",
                text="Source",
                pages=(),
            )
        ),
        extract_fields=AsyncMock(
            return_value=FieldExtractionResult(
                schema_id="paper.rent_invoice", schema_version="1", data={}
            )
        ),
    )
    return await PaperExtractionProcessor(AsyncMock(return_value=service)).process(
        str(source),
        {
            "workflow": "paper_extraction",
            "schema_name": "rent_invoice",
            "content_mode": "text",
            "original_filename": "invoice.pdf",
            "file_size": 8,
        },
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("backend", ["memory", "redis"])
@pytest.mark.parametrize("failure_stage", ["before_commit", "ambiguous_commit"])
async def test_result_artifact_ownership_matches_completion_commit_boundary(
    backend: str, failure_stage: str, tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("UPLOADS_DIR", str(tmp_path))
    output = await _owned_output(tmp_path)
    artifact = tmp_path / output["chunks"][0]["artifact_name"]
    job = SimpleNamespace(
        id="job-1",
        file_path="source.pdf",
        tenant_id="tenant-a",
        meta={"workflow": "paper_extraction"},
    )
    module = "src.ingestion.queue_manager" if backend == "memory" else "src.ingestion.redis_queue"
    with (
        patch("src.db.session.session_manager") as manager,
        patch(f"{module}.IngestionService") as jobs,
        patch(f"{module}.DocumentService") as documents,
    ):
        session = AsyncMock()
        manager.session.return_value.__aenter__.return_value = session
        jobs.return_value.update_status = AsyncMock(return_value=job)
        jobs.return_value.mark_completed = AsyncMock()
        jobs.return_value.mark_failed = AsyncMock()
        documents.return_value.create_document = AsyncMock()
        if failure_stage == "before_commit":
            documents.return_value.create_document.side_effect = RuntimeError("Storage unavailable")
        else:
            session.commit.side_effect = [
                None,
                RuntimeError("Commit acknowledgement unavailable"),
                None,
            ]
        if backend == "memory":
            queue = IngestionQueue(
                AsyncMock(), workflow_handlers={"paper_extraction": AsyncMock(return_value=output)}
            )
            await queue.queue.put("job-1")
            await queue.start_worker()
            await asyncio.wait_for(queue.queue.join(), timeout=3)
            await queue.stop_worker()
        else:
            queue = RedisIngestionQueue(
                AsyncMock(), workflow_handlers={"paper_extraction": AsyncMock(return_value=output)}
            )
            queue._handle_failure = AsyncMock()
            await queue._process_job("job-1", worker_id=0)
    assert artifact.exists() is (failure_stage == "ambiguous_commit")
    assert (tmp_path / "source.pdf").exists()


@pytest.mark.asyncio
async def test_post_commit_redis_housekeeping_failure_never_retries_completed_job(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("UPLOADS_DIR", str(tmp_path))
    (tmp_path / "source.pdf").write_bytes(b"%PDF-1.7")
    job = SimpleNamespace(
        file_path="source.pdf", tenant_id="tenant-a", meta={"workflow": "paper_extraction"}
    )
    with (
        patch("src.db.session.session_manager") as manager,
        patch("src.ingestion.redis_queue.IngestionService") as jobs,
        patch("src.ingestion.redis_queue.DocumentService") as documents,
    ):
        manager.session.return_value.__aenter__.return_value = AsyncMock()
        jobs.return_value.update_status = AsyncMock(return_value=job)
        jobs.return_value.mark_completed = AsyncMock()
        documents.return_value.create_document = AsyncMock()
        queue = RedisIngestionQueue(
            AsyncMock(),
            workflow_handlers={
                "paper_extraction": AsyncMock(return_value={"content": "text", "chunks": []})
            },
        )
        queue._redis = AsyncMock()
        queue._redis.delete.side_effect = ConnectionError("Redis housekeeping unavailable")
        queue._handle_failure = AsyncMock()
        await queue._process_job("job-1", worker_id=0)
        jobs.return_value.mark_completed.assert_awaited_once()
        queue._handle_failure.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("backend", ["memory", "redis"])
async def test_graceful_cancellation_returns_paper_job_to_pending_queue(
    backend: str, tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("UPLOADS_DIR", str(tmp_path))
    (tmp_path / "source.pdf").write_bytes(b"%PDF-1.7")
    started = asyncio.Event()

    async def wait_for_stop(*args):
        started.set()
        await asyncio.Event().wait()

    job = SimpleNamespace(
        id="job-1",
        file_path="source.pdf",
        tenant_id="tenant-a",
        status=IngestionStatus.PROCESSING,
        meta={"workflow": "paper_extraction"},
    )
    module = "src.ingestion.queue_manager" if backend == "memory" else "src.ingestion.redis_queue"
    with (
        patch("src.db.session.session_manager") as manager,
        patch(f"{module}.IngestionService") as jobs,
    ):
        manager.session.return_value.__aenter__.return_value = AsyncMock()
        jobs.return_value.update_status = AsyncMock(return_value=job)
        jobs.return_value.get_by_id = AsyncMock(return_value=job)
        jobs.return_value.mark_failed = AsyncMock()
        if backend == "memory":
            queue = IngestionQueue(
                AsyncMock(), workflow_handlers={"paper_extraction": wait_for_stop}
            )
            await queue.queue.put("job-1")
            await queue.start_worker()
            await asyncio.wait_for(started.wait(), timeout=2)
            await queue.stop_worker()
            assert queue.queue.get_nowait() == "job-1"
        else:
            queue = RedisIngestionQueue(
                AsyncMock(), workflow_handlers={"paper_extraction": wait_for_stop}
            )
            queue._redis = AsyncMock()
            task = asyncio.create_task(queue._process_job("job-1", worker_id=0))
            await asyncio.wait_for(started.wait(), timeout=2)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            queue._redis.rpush.assert_awaited_once_with(queue.queue_key, "job-1")
        assert any(
            call.args[:2] == ("job-1", IngestionStatus.PENDING)
            for call in jobs.return_value.update_status.call_args_list
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("backend", ["memory", "redis"])
@pytest.mark.parametrize("cancelled", [False, True])
async def test_paper_submission_preserves_owner_when_commit_outcome_is_uncertain(
    backend: str, cancelled: bool
) -> None:
    module = "src.ingestion.queue_manager" if backend == "memory" else "src.ingestion.redis_queue"
    with (
        patch("src.db.session.session_manager") as manager,
        patch(f"{module}.IngestionService") as jobs,
    ):
        session = AsyncMock()
        manager.session.return_value.__aenter__.return_value = session
        jobs.return_value.create_job = AsyncMock(return_value=SimpleNamespace(id="owned-job"))
        session.commit.side_effect = (
            asyncio.CancelledError()
            if cancelled
            else ConnectionError("Private connection information")
        )
        queue = (
            IngestionQueue(AsyncMock()) if backend == "memory" else RedisIngestionQueue(AsyncMock())
        )
        expected = QueueSubmissionCancelledError if cancelled else QueueSubmissionError
        with pytest.raises(expected) as error:
            await queue.enqueue(
                "source.pdf", meta={"workflow": "paper_extraction"}, tenant_id="tenant-a"
            )
        assert error.value.persisted_job_id == "owned-job"
        assert "Private" not in str(error.value)


@pytest.mark.asyncio
async def test_paper_publication_failure_retains_typed_owner_even_when_status_write_fails() -> None:
    with (
        patch("src.db.session.session_manager") as manager,
        patch("src.ingestion.redis_queue.IngestionService") as jobs,
    ):
        manager.session.return_value.__aenter__.return_value = AsyncMock()
        jobs.return_value.create_job = AsyncMock(return_value=SimpleNamespace(id="owned-job"))
        jobs.return_value.mark_failed = AsyncMock(
            side_effect=ConnectionError("Status connection failed")
        )
        queue = RedisIngestionQueue(AsyncMock())
        queue._redis = AsyncMock()
        queue._redis.rpush.side_effect = ConnectionError("Publication connection failed")
        with pytest.raises(QueueSubmissionError) as error:
            await queue.enqueue(
                "source.pdf", meta={"workflow": "paper_extraction"}, tenant_id="tenant-a"
            )
        assert error.value.persisted_job_id == "owned-job"


@pytest.mark.asyncio
async def test_interrupted_publication_failure_becomes_safe_failed_history() -> None:
    job = SimpleNamespace(status=IngestionStatus.PROCESSING, meta={"workflow": "paper_extraction"})
    with patch("src.db.session.session_manager") as manager:
        manager.session.return_value.__aenter__.return_value = AsyncMock()
        service = SimpleNamespace(
            get_by_id=AsyncMock(return_value=job),
            update_status=AsyncMock(),
            mark_failed=AsyncMock(),
        )
        await recover_interrupted_workflow(
            "job-1",
            AsyncMock(side_effect=ConnectionError("Private backend")),
            service_factory=lambda session: service,
        )
        service.mark_failed.assert_awaited_once_with(
            "job-1", "Processing was interrupted before completion. Retry the stored upload."
        )


@pytest.mark.asyncio
async def test_interrupted_completed_job_is_not_requeued_or_changed() -> None:
    job = SimpleNamespace(status=IngestionStatus.COMPLETED, meta={"workflow": "paper_extraction"})
    with patch("src.db.session.session_manager") as manager:
        manager.session.return_value.__aenter__.return_value = AsyncMock()
        service = SimpleNamespace(
            get_by_id=AsyncMock(return_value=job),
            update_status=AsyncMock(),
            mark_failed=AsyncMock(),
        )
        publish = AsyncMock()
        await recover_interrupted_workflow(
            "job-1", publish, service_factory=lambda session: service
        )
        publish.assert_not_awaited()
        service.update_status.assert_not_awaited()
        service.mark_failed.assert_not_awaited()


@pytest.mark.asyncio
async def test_cancellation_during_artifact_write_does_not_leave_unowned_output(
    tmp_path: Path, monkeypatch
) -> None:
    import threading

    import src.services.paper_extraction as processing

    monkeypatch.setenv("UPLOADS_DIR", str(tmp_path))
    started, release = threading.Event(), threading.Event()
    original = processing._store_artifact

    def delayed_write(*args):
        started.set()
        release.wait(timeout=3)
        return original(*args)

    with patch("src.services.paper_extraction._store_artifact", side_effect=delayed_write):
        task = asyncio.create_task(_owned_output(tmp_path))
        assert await asyncio.to_thread(started.wait, 2)
        task.cancel()
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        await asyncio.sleep(0.05)
    assert not list(tmp_path.glob("*.paper-extraction.json"))
    assert not list(tmp_path.glob("*.tmp"))
