"""Persist successful, partial and failed PAPER run usage independently of fields."""

import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from src.db.models.ingestion import IngestionStatus
from src.extraction.contracts import (
    DocumentResult,
    FieldExtractionResult,
    ModelDescriptor,
    ModelRequest,
    ModelResponse,
)
from src.extraction.errors import ExtractionError
from src.extraction.model_gateway import ModelGateway
from src.extraction.ports import BaseGenerationProvider
from src.paper.extraction_contracts import PaperExtractionResult
from src.services.ingestion import IngestionService
from src.services.paper_extraction import PaperExtractionProcessor


class MeteredProvider(BaseGenerationProvider):
    @property
    def descriptor(self) -> ModelDescriptor:
        return ModelDescriptor(model_id="test-model")

    async def complete(self, request: ModelRequest) -> ModelResponse:
        return ModelResponse(
            content="ok", model_id="test-model", usage={"input_tokens": 10, "output_tokens": 5}
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("fail_stage", [None, "fields", "document", "artifact"])
async def test_processor_records_all_calls_and_retains_partial_or_failed_usage(
    fail_stage: str | None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("UPLOADS_DIR", str(tmp_path))
    source = tmp_path / "source.pdf"
    source.write_bytes(b"%PDF-1.7")
    gateway = ModelGateway({"vision": MeteredProvider(), "fields": MeteredProvider()})

    async def document(*args: object) -> DocumentResult:
        await gateway.generate("vision", ModelRequest(prompt="source", purpose="ocr"))
        if fail_stage == "document":
            raise ExtractionError("workflow_timeout", "private provider detail")
        return DocumentResult(
            document_id="source-hash",
            source_name="source.pdf",
            content_mode="text",
            text="invoice",
            pages=(),
        )

    async def fields(*args: object, **kwargs: object) -> FieldExtractionResult:
        await gateway.generate("fields", ModelRequest(prompt="source"))
        await gateway.generate("fields", ModelRequest(prompt="repair"))
        if fail_stage == "fields":
            raise ExtractionError("schema_validation_failed", "private provider detail")
        return FieldExtractionResult(schema_id="paper.rent_invoice", schema_version="1", data={})

    service = SimpleNamespace(extract_document=document, extract_fields=fields)
    processor = PaperExtractionProcessor(AsyncMock(return_value=service))
    parameters = {
        "workflow": "paper_extraction",
        "schema_name": "rent_invoice",
        "content_mode": "text",
        "original_filename": "source.pdf",
        "file_size": 8,
    }
    if fail_stage == "artifact":

        def fail_storage(*args: object) -> str:
            raise OSError("private path and document details")

        monkeypatch.setattr("src.services.paper_extraction._store_artifact", fail_storage)
        with pytest.raises(ExtractionError) as caught:
            await processor.process(str(source), parameters)
        assert caught.value.usage_summary.call_count == 3
        assert caught.value.usage_summary.total_tokens == 45
        assert "private" not in str(caught.value)
        return
    if fail_stage == "document":
        with pytest.raises(ExtractionError) as caught:
            await processor.process(str(source), parameters)
        assert caught.value.usage_summary.total_tokens == 15
        assert caught.value.usage_summary.call_count == 1
        assert "private" not in str(caught.value)
        return
    output = await processor.process(str(source), parameters)
    usage = output["job_metadata"]["usage"]
    assert usage["call_count"] == 3
    assert usage["total_tokens"] == 45
    artifact = tmp_path / output["chunks"][0]["artifact_name"]
    result = PaperExtractionResult.model_validate_json(artifact.read_text())
    assert result.usage.model_dump(mode="json") == usage
    assert [call.purpose for call in result.usage.calls] == ["ocr", "fields", "fields"]
    # A retry of the same persisted job includes earlier attempts; an API retry
    # creates a new job with only validated input parameters and starts afresh.
    output2 = await processor.process(str(source), {**parameters, "usage": usage})
    assert output2["job_metadata"]["usage"]["call_count"] == 6
    assert output2["job_metadata"]["usage"]["total_tokens"] == 90


@pytest.mark.asyncio
async def test_mark_failed_persists_only_typed_usage_and_preserves_old_call_shape() -> None:
    from src.extraction.usage import capture_model_usage

    with capture_model_usage() as meter:
        await ModelGateway({"fields": MeteredProvider()}).generate(
            "fields", ModelRequest(prompt="x")
        )
    service = IngestionService(AsyncMock())
    service.update_status = AsyncMock()
    await service.mark_failed("job", "safe error", usage=meter.snapshot())
    service.update_status.assert_awaited_once_with(
        "job",
        IngestionStatus.FAILED,
        {"error": "safe error", "usage": meter.snapshot().model_dump(mode="json")},
    )
    service.update_status.reset_mock()
    await service.mark_failed("legacy", "safe error")
    service.update_status.assert_awaited_once_with(
        "legacy", IngestionStatus.FAILED, {"error": "safe error"}
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("backend", ["memory", "redis"])
@pytest.mark.parametrize("fail_after_result", [False, True])
async def test_queue_failure_forwards_typed_ledger_without_weakening_legacy_errors(
    backend: str, fail_after_result: bool, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from src.extraction.usage import capture_model_usage
    from src.ingestion.queue_manager import IngestionQueue
    from src.ingestion.redis_queue import RedisIngestionQueue
    from src.ingestion.workflow_result import QueuedWorkflowResult

    monkeypatch.setenv("UPLOADS_DIR", str(tmp_path))
    (tmp_path / "source.pdf").write_bytes(b"%PDF-1.7")
    with capture_model_usage() as meter:
        await ModelGateway({"fields": MeteredProvider()}).generate(
            "fields", ModelRequest(prompt="x")
        )
    ledger = meter.snapshot()
    handler = AsyncMock(
        side_effect=ExtractionError("workflow_timeout", "safe error", usage_summary=ledger)
    )
    if fail_after_result:
        handler = AsyncMock(
            return_value=QueuedWorkflowResult(
                {"content": "source", "job_metadata": {"usage": ledger.model_dump(mode="json")}},
                discard=AsyncMock(),
            )
        )
    job = SimpleNamespace(
        id="job", tenant_id="tenant", file_path="source.pdf", meta={"workflow": "paper_extraction"}
    )
    module = "src.ingestion.queue_manager" if backend == "memory" else "src.ingestion.redis_queue"
    with (
        patch("src.db.session.session_manager") as manager,
        patch(f"{module}.IngestionService") as jobs,
        patch(f"{module}.DocumentService") as documents,
    ):
        manager.session.return_value.__aenter__.return_value = AsyncMock()
        jobs.return_value.update_status = AsyncMock(return_value=job)
        jobs.return_value.mark_failed = AsyncMock()
        jobs.return_value.mark_completed = AsyncMock()
        documents.return_value.create_document = AsyncMock(side_effect=RuntimeError("safe error"))
        if backend == "memory":
            queue = IngestionQueue(AsyncMock(), workflow_handlers={"paper_extraction": handler})
            await queue.queue.put("job")
            await queue.start_worker()
            await asyncio.wait_for(queue.queue.join(), 2)
            await queue.stop_worker()
            jobs.return_value.mark_failed.assert_awaited_once_with(
                "job", "safe error", usage=ledger
            )
        else:
            queue = RedisIngestionQueue(
                AsyncMock(), workflow_handlers={"paper_extraction": handler}
            )
            queue._handle_failure = AsyncMock()
            await queue._process_job("job", 0)
            queue._handle_failure.assert_awaited_once_with(
                "job", "safe error", workflow="paper_extraction", usage=ledger
            )


@pytest.mark.asyncio
async def test_processor_cancellation_retains_completed_and_unknown_inflight_calls(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from src.extraction.cancelled_error import ExtractionCancelledError

    monkeypatch.setenv("UPLOADS_DIR", str(tmp_path))
    source = tmp_path / "source.pdf"
    source.write_bytes(b"%PDF-1.7")
    started = asyncio.Event()
    provider = MeteredProvider()
    gateway = ModelGateway({"vision": provider})

    async def wait_model(request: ModelRequest) -> ModelResponse:
        started.set()
        await asyncio.Event().wait()
        raise AssertionError("unreachable")

    async def document(*args: object) -> DocumentResult:
        await gateway.generate("vision", ModelRequest(prompt="first", purpose="ocr"))
        provider.complete = wait_model
        await gateway.generate("vision", ModelRequest(prompt="second", purpose="ocr"))
        raise AssertionError("unreachable")

    processor = PaperExtractionProcessor(
        AsyncMock(return_value=SimpleNamespace(extract_document=document))
    )
    task = asyncio.create_task(
        processor.process(
            str(source),
            {
                "workflow": "paper_extraction",
                "schema_name": "rent_invoice",
                "content_mode": "text",
                "original_filename": "source.pdf",
                "file_size": 8,
            },
        )
    )
    await asyncio.wait_for(started.wait(), 2)
    task.cancel()
    with pytest.raises(ExtractionCancelledError) as caught:
        await task
    assert caught.value.usage_summary.call_count == 2
    assert caught.value.usage_summary.total_tokens == 15
    assert caught.value.usage_summary.coverage == "partial"
    assert caught.value.usage_summary.calls[1].status == "cancelled"


@pytest.mark.asyncio
async def test_recovery_and_redis_backoff_durably_retain_usage() -> None:
    from src.extraction.usage import capture_model_usage
    from src.ingestion.redis_queue import RedisIngestionQueue
    from src.ingestion.workflow_recovery import recover_interrupted_workflow

    with capture_model_usage() as meter:
        await ModelGateway({"fields": MeteredProvider()}).generate(
            "fields", ModelRequest(prompt="x")
        )
    ledger = meter.snapshot()
    job = SimpleNamespace(status=IngestionStatus.PROCESSING, meta={"workflow": "paper_extraction"})
    service = SimpleNamespace(get_by_id=AsyncMock(return_value=job), update_status=AsyncMock())
    with patch("src.db.session.session_manager") as manager:
        manager.session.return_value.__aenter__.return_value = AsyncMock()
        await recover_interrupted_workflow(
            "job", AsyncMock(), service_factory=lambda session: service, usage=ledger
        )
        service.update_status.assert_awaited_once_with(
            "job",
            IngestionStatus.PENDING,
            {"interrupted": True, "usage": ledger.model_dump(mode="json")},
        )
        service.update_status.reset_mock()
        queue = RedisIngestionQueue(AsyncMock())
        queue._redis = AsyncMock()
        queue._redis.incr.return_value = 1
        with (
            patch("src.ingestion.redis_queue.IngestionService", return_value=service),
            patch("src.ingestion.redis_queue.asyncio.sleep", side_effect=asyncio.CancelledError),
            pytest.raises(asyncio.CancelledError),
        ):
            await queue._handle_failure("job", "safe", workflow="paper_extraction", usage=ledger)
        service.update_status.assert_awaited_once_with(
            "job", IngestionStatus.PROCESSING, {"usage": ledger.model_dump(mode="json")}
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("backend", ["memory", "redis"])
async def test_workers_forward_cancelled_attempt_usage_into_recovery(
    backend: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from src.extraction.cancelled_error import ExtractionCancelledError
    from src.extraction.usage import capture_model_usage
    from src.ingestion.queue_manager import IngestionQueue
    from src.ingestion.redis_queue import RedisIngestionQueue

    monkeypatch.setenv("UPLOADS_DIR", str(tmp_path))
    (tmp_path / "source.pdf").write_bytes(b"%PDF-1.7")
    with capture_model_usage() as meter:
        await ModelGateway({"fields": MeteredProvider()}).generate(
            "fields", ModelRequest(prompt="x")
        )
    ledger = meter.snapshot()
    handler = AsyncMock(side_effect=ExtractionCancelledError(ledger))
    job = SimpleNamespace(
        id="job", tenant_id="tenant", file_path="source.pdf", meta={"workflow": "paper_extraction"}
    )
    module = "src.ingestion.queue_manager" if backend == "memory" else "src.ingestion.redis_queue"
    with (
        patch("src.db.session.session_manager") as manager,
        patch(f"{module}.IngestionService") as jobs,
        patch(f"{module}.recover_interrupted_workflow", new_callable=AsyncMock) as recover,
    ):
        manager.session.return_value.__aenter__.return_value = AsyncMock()
        jobs.return_value.update_status = AsyncMock(return_value=job)
        if backend == "memory":
            queue = IngestionQueue(AsyncMock(), workflow_handlers={"paper_extraction": handler})
            await queue.queue.put("job")
            await queue.start_worker()
            await asyncio.wait_for(queue.queue.join(), 2)
            await queue.stop_worker()
        else:
            queue = RedisIngestionQueue(
                AsyncMock(), workflow_handlers={"paper_extraction": handler}
            )
            with pytest.raises(asyncio.CancelledError):
                await queue._process_job("job", 0)
        recover.assert_awaited_once_with("job", queue.requeue, service_factory=jobs, usage=ledger)
