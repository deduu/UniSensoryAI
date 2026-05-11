"""Tests for src/ingestion/redis_queue.py — Redis queue logic (no real Redis needed).

Tests verify retry/backoff/DLQ behavior by mocking the Redis client.
"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Mock heavy ML modules
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

from src.db.models.ingestion import IngestionJob, IngestionStatus
from src.ingestion.redis_queue import (
    MAX_RETRIES,
    RedisIngestionQueue,
)


@pytest.fixture
def mock_redis():
    """Mock aioredis client."""
    mock = AsyncMock()
    mock.rpush = AsyncMock()
    mock.blpop = AsyncMock(return_value=None)
    mock.llen = AsyncMock(return_value=0)
    mock.incr = AsyncMock(return_value=1)
    mock.delete = AsyncMock()
    mock.aclose = AsyncMock()
    return mock


@pytest.fixture
def queue(mock_redis):
    """RedisIngestionQueue with mocked Redis."""
    q = RedisIngestionQueue(
        processing_function=AsyncMock(return_value={"content": "ok"}),
        redis_url="redis://localhost:6379",
        concurrency=1,
        gpu_semaphore_limit=1,
    )
    q._redis = mock_redis
    return q


class TestRedisIngestionQueue:
    @pytest.mark.asyncio
    async def test_enqueue_creates_db_record_and_pushes(self, queue, mock_redis):
        """enqueue should create a DB job and push to Redis."""
        with patch("src.db.session.session_manager") as mock_manager:
            mock_session = AsyncMock()
            mock_manager.session.return_value.__aenter__.return_value = mock_session

            with patch(
                "src.ingestion.redis_queue.IngestionService"
            ) as MockService:
                mock_job = MagicMock(spec=IngestionJob)
                mock_job.id = "redis-job-1"
                MockService.return_value.create_job = AsyncMock(
                    return_value=mock_job
                )

                job_id = await queue.enqueue(
                    "test.pdf", meta={"model_id": "gpt-4o"}, tenant_id="t-1"
                )

        assert job_id == "redis-job-1"
        mock_redis.rpush.assert_called_once_with("unisensory:jobs", "redis-job-1")

    @pytest.mark.asyncio
    async def test_get_queue_depth(self, queue, mock_redis):
        """get_queue_depth should call llen on the queue key."""
        mock_redis.llen.return_value = 5
        depth = await queue.get_queue_depth()
        assert depth == 5
        mock_redis.llen.assert_called_with("unisensory:jobs")

    @pytest.mark.asyncio
    async def test_get_dlq_depth(self, queue, mock_redis):
        """get_dlq_depth should call llen on the DLQ key."""
        mock_redis.llen.return_value = 2
        depth = await queue.get_dlq_depth()
        assert depth == 2
        mock_redis.llen.assert_called_with("unisensory:dlq")

    @pytest.mark.asyncio
    async def test_handle_failure_retries(self, queue, mock_redis):
        """First failure should re-enqueue with retry count."""
        mock_redis.incr.return_value = 1  # First retry

        with patch("src.db.session.session_manager") as mock_manager:
            mock_session = AsyncMock()
            mock_manager.session.return_value.__aenter__.return_value = mock_session

            with patch("src.ingestion.redis_queue.IngestionService") as MockService:
                MockService.return_value.mark_failed = AsyncMock()

                await queue._handle_failure("job-1", "test error")

        # Should re-enqueue
        mock_redis.rpush.assert_called_with("unisensory:jobs", "job-1")
        # Should NOT move to DLQ
        assert not any(
            call.args[0] == "unisensory:dlq" for call in mock_redis.rpush.call_args_list
            if len(call.args) > 0 and call.args[0] == "unisensory:dlq"
        )

    @pytest.mark.asyncio
    async def test_handle_failure_moves_to_dlq_after_max_retries(
        self, queue, mock_redis
    ):
        """After MAX_RETRIES, job should be moved to DLQ."""
        mock_redis.incr.return_value = MAX_RETRIES + 1  # Exceeded

        with patch("src.db.session.session_manager") as mock_manager:
            mock_session = AsyncMock()
            mock_manager.session.return_value.__aenter__.return_value = mock_session

            with patch("src.ingestion.redis_queue.IngestionService") as MockService:
                MockService.return_value.mark_failed = AsyncMock()

                await queue._handle_failure("job-1", "persistent error")

        # Should push to DLQ
        dlq_calls = [
            call for call in mock_redis.rpush.call_args_list
            if call.args[0] == "unisensory:dlq"
        ]
        assert len(dlq_calls) == 1
        # Should delete retry counter
        mock_redis.delete.assert_called_with(f"{queue.retry_key_prefix}job-1")

    @pytest.mark.asyncio
    async def test_process_job_success_clears_retry_counter(
        self, queue, mock_redis
    ):
        """Successful processing should delete the retry counter."""
        with patch("src.db.session.session_manager") as mock_manager:
            mock_session = AsyncMock()
            mock_manager.session.return_value.__aenter__.return_value = mock_session

            with patch(
                "src.ingestion.redis_queue.IngestionService"
            ) as MockService:
                mock_job = MagicMock()
                mock_job.file_path = "test.pdf"
                mock_job.tenant_id = "t-1"
                mock_job.meta = {"model_id": "test"}
                MockService.return_value.update_status = AsyncMock(
                    return_value=mock_job
                )
                MockService.return_value.mark_completed = AsyncMock()

                with patch(
                    "src.ingestion.redis_queue.DocumentService"
                ) as MockDocService:
                    MockDocService.return_value.create_document = AsyncMock()

                    await queue._process_job("job-1", worker_id=0)

        mock_redis.delete.assert_called_with(f"{queue.retry_key_prefix}job-1")

    @pytest.mark.asyncio
    async def test_start_stop_workers(self, queue):
        """start_worker/stop_worker should manage worker tasks."""
        await queue.start_worker()
        assert queue.is_running is True
        assert len(queue._worker_tasks) == 1  # concurrency=1

        await queue.stop_worker()
        assert queue.is_running is False
        assert len(queue._worker_tasks) == 0

    @pytest.mark.asyncio
    async def test_gpu_semaphore_limits_concurrency(self, queue, mock_redis):
        """GPU semaphore should gate concurrent inference."""
        assert queue._gpu_semaphore._value == 1  # gpu_semaphore_limit=1
