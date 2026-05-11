"""Tests for src/ingestion/queue_manager.py — queue flow, error handling, model_id threading."""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from src.ingestion.queue_manager import IngestionQueue
from src.db.models.ingestion import IngestionJob, IngestionStatus


@pytest.mark.asyncio
async def test_ingestion_queue_flow():
    """Happy path: enqueue -> process -> complete."""
    with patch("src.db.session.session_manager") as mock_manager:
        mock_session = AsyncMock()
        mock_manager.session.return_value.__aenter__.return_value = mock_session

        with patch("src.ingestion.queue_manager.IngestionService") as MockServiceArg:
            mock_service_instance = MockServiceArg.return_value

            mock_job = MagicMock(spec=IngestionJob)
            mock_job.id = "test-job-id"
            mock_job.file_path = "test.pdf"
            mock_job.tenant_id = "t-1"
            mock_job.meta = {"model_id": "qwen2-vl-2b-instruct"}

            mock_service_instance.create_job = AsyncMock(return_value=mock_job)
            mock_service_instance.update_status = AsyncMock(return_value=mock_job)
            mock_service_instance.mark_completed = AsyncMock(return_value=mock_job)

            with patch("src.ingestion.queue_manager.DocumentService") as MockDocService:
                mock_doc_service = MockDocService.return_value
                mock_doc_service.create_document = AsyncMock()

                async def dummy_processor(file_path, model_id):
                    await asyncio.sleep(0.01)
                    return {"content": "processed", "page_count": 1}

                queue = IngestionQueue(dummy_processor)

                job_id = await queue.enqueue("test.pdf", tenant_id="t-1")
                assert job_id == "test-job-id"
                mock_service_instance.create_job.assert_called_once()
                assert (
                    mock_service_instance.create_job.call_args.kwargs["tenant_id"]
                    == "t-1"
                )

                await queue.start_worker()
                await asyncio.sleep(0.2)

                mock_service_instance.update_status.assert_any_call(
                    "test-job-id", IngestionStatus.PROCESSING
                )
                mock_service_instance.mark_completed.assert_called_once()

                await queue.stop_worker()


@pytest.mark.asyncio
async def test_ingestion_queue_worker_error():
    """Error path: processing failure marks job as failed."""
    with patch("src.db.session.session_manager") as mock_manager:
        mock_session = AsyncMock()
        mock_manager.session.return_value.__aenter__.return_value = mock_session

        with patch("src.ingestion.queue_manager.IngestionService") as MockServiceArg:
            mock_service_instance = MockServiceArg.return_value
            mock_job = MagicMock(spec=IngestionJob)
            mock_job.id = "error-job-id"
            mock_job.file_path = "error.pdf"
            mock_job.tenant_id = "t-1"
            mock_job.meta = {}

            mock_service_instance.create_job = AsyncMock(return_value=mock_job)
            mock_service_instance.update_status = AsyncMock(return_value=mock_job)
            mock_service_instance.mark_failed = AsyncMock(return_value=mock_job)

            async def error_processor(file_path, model_id):
                raise ValueError("Processing failed")

            queue = IngestionQueue(error_processor)

            await queue.enqueue("error.pdf", tenant_id="t-1")
            await queue.start_worker()
            await asyncio.sleep(0.2)

            mock_service_instance.mark_failed.assert_called_with(
                "error-job-id", "Processing failed"
            )

            await queue.stop_worker()


@pytest.mark.asyncio
async def test_worker_passes_model_id_from_meta():
    """Worker should extract model_id from job.meta and pass to processing_function."""
    with patch("src.db.session.session_manager") as mock_manager:
        mock_session = AsyncMock()
        mock_manager.session.return_value.__aenter__.return_value = mock_session

        with patch("src.ingestion.queue_manager.IngestionService") as MockServiceArg:
            mock_service_instance = MockServiceArg.return_value

            mock_job = MagicMock(spec=IngestionJob)
            mock_job.id = "model-test-job"
            mock_job.file_path = "doc.pdf"
            mock_job.tenant_id = "t-1"
            mock_job.meta = {"model_id": "gpt-4o"}

            mock_service_instance.create_job = AsyncMock(return_value=mock_job)
            mock_service_instance.update_status = AsyncMock(return_value=mock_job)
            mock_service_instance.mark_completed = AsyncMock(return_value=mock_job)

            with patch("src.ingestion.queue_manager.DocumentService") as MockDocService:
                mock_doc_service = MockDocService.return_value
                mock_doc_service.create_document = AsyncMock()

                processor_mock = AsyncMock(return_value={"content": "ok"})
                queue = IngestionQueue(processor_mock)

                await queue.enqueue("doc.pdf", meta={"model_id": "gpt-4o"}, tenant_id="t-1")
                await queue.start_worker()
                await asyncio.sleep(0.2)

                processor_mock.assert_called_once_with("doc.pdf", "gpt-4o")

                await queue.stop_worker()


@pytest.mark.asyncio
async def test_worker_defaults_model_id_when_missing():
    """Worker should use default model_id when meta has no model_id."""
    with patch("src.db.session.session_manager") as mock_manager:
        mock_session = AsyncMock()
        mock_manager.session.return_value.__aenter__.return_value = mock_session

        with patch("src.ingestion.queue_manager.IngestionService") as MockServiceArg:
            mock_service_instance = MockServiceArg.return_value

            mock_job = MagicMock(spec=IngestionJob)
            mock_job.id = "default-model-job"
            mock_job.file_path = "doc.pdf"
            mock_job.tenant_id = "t-1"
            mock_job.meta = {}

            mock_service_instance.create_job = AsyncMock(return_value=mock_job)
            mock_service_instance.update_status = AsyncMock(return_value=mock_job)
            mock_service_instance.mark_completed = AsyncMock(return_value=mock_job)

            with patch("src.ingestion.queue_manager.DocumentService") as MockDocService:
                mock_doc_service = MockDocService.return_value
                mock_doc_service.create_document = AsyncMock()

                processor_mock = AsyncMock(return_value={"content": "ok"})
                queue = IngestionQueue(processor_mock)

                await queue.enqueue("doc.pdf", meta={}, tenant_id="t-1")
                await queue.start_worker()
                await asyncio.sleep(0.2)

                processor_mock.assert_called_once_with("doc.pdf", "qwen2-vl-2b-instruct")

                await queue.stop_worker()
