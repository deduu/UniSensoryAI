"""Redis-backed persistent ingestion queue with concurrent workers.

This module provides ``RedisIngestionQueue``, a drop-in replacement for
the in-memory ``IngestionQueue`` that persists jobs in Redis and supports
concurrent workers with GPU semaphore, dead letter queue, and exponential
backoff on retries.

Requires ``redis`` package::

    pip install redis

Usage::

    queue = RedisIngestionQueue(
        processing_function=process_document_job,
        redis_url="redis://localhost:6379",
        concurrency=4,
    )
    await queue.start_worker()
"""

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable, Mapping
from pathlib import Path
from typing import Any

import src.db.session as db_session
from src.db.models.ingestion import IngestionStatus
from src.extraction.cancelled_error import ExtractionCancelledError
from src.extraction.contracts.usage import ExtractionUsage
from src.extraction.errors import ExtractionError
from src.ingestion.submission_cancelled_error import QueueSubmissionCancelledError
from src.ingestion.submission_error import QueueSubmissionError
from src.ingestion.workflow_recovery import recover_interrupted_workflow
from src.ingestion.workflow_result import QueuedWorkflowResult
from src.services.document import DocumentService
from src.services.ingestion import IngestionService
from src.services.upload_storage import resolve_upload_path

logger = logging.getLogger(__name__)
WorkflowHandler = Callable[[str, dict[str, Any]], Awaitable[dict[str, Any]]]

# Retry constants
MAX_RETRIES = 3
INITIAL_BACKOFF_S = 1.0
MAX_BACKOFF_S = 60.0
BACKOFF_MULTIPLIER = 2.0


class RedisIngestionQueue:
    """Redis-backed persistent job queue with concurrent workers.

    Jobs are persisted as Redis list entries so they survive process restarts.
    Multiple worker coroutines consume from the list concurrently, with a
    GPU semaphore controlling how many can run inference simultaneously.

    Jobs that fail ``MAX_RETRIES`` times are moved to a dead letter queue.

    Attributes:
        redis_url: Redis connection URL.
        concurrency: Number of concurrent worker coroutines.
        gpu_semaphore_limit: Max concurrent GPU inference tasks.
        queue_key: Redis key for the main job queue.
        dlq_key: Redis key for the dead letter queue.
    """

    def __init__(
        self,
        processing_function: Callable[..., Awaitable[Any]],
        redis_url: str = "redis://localhost:6379",
        concurrency: int = 4,
        gpu_semaphore_limit: int = 1,
        queue_key: str = "unisensory:jobs",
        dlq_key: str = "unisensory:dlq",
        workflow_handlers: Mapping[str, WorkflowHandler] | None = None,
    ) -> None:
        self.processing_function = processing_function
        self.workflow_handlers = dict(workflow_handlers or {})
        self.redis_url = redis_url
        self.concurrency = concurrency
        self.gpu_semaphore_limit = gpu_semaphore_limit
        self.queue_key = queue_key
        self.dlq_key = dlq_key
        self.retry_key_prefix = "unisensory:retries:"

        self._redis = None
        self.is_running = False
        self._worker_tasks: list[asyncio.Task] = []
        self._gpu_semaphore = asyncio.Semaphore(gpu_semaphore_limit)

    async def _get_redis(self):
        """Lazy-init Redis connection."""
        if self._redis is None:
            try:
                import redis.asyncio as aioredis
            except ImportError:
                raise ImportError(
                    "redis package is required for RedisIngestionQueue. "
                    "Install it with: pip install redis"
                )
            self._redis = aioredis.from_url(self.redis_url, decode_responses=True)
        return self._redis

    async def enqueue(
        self,
        file_path: str,
        meta: dict | None = None,
        *,
        tenant_id: str,
    ) -> str:
        """Create a DB record and enqueue job_id to Redis.

        Args:
            file_path: Path to the uploaded file.
            meta: Optional metadata dict (model_id, api_keys, etc).
            tenant_id: Owning tenant for the job (NOT NULL on the row).

        Returns:
            The created job_id string.
        """
        if db_session.session_manager is None:
            raise RuntimeError("DatabaseSessionManager is not initialized! Call init_db first.")

        is_paper = (meta or {}).get("workflow") == "paper_extraction"
        commit_started = False
        job_id = None
        try:
            async with db_session.session_manager.session() as session:
                service = IngestionService(session)
                job = await service.create_job(file_path, meta, tenant_id=tenant_id)
                job_id = job.id
                commit_started = True
                await session.commit()
        except asyncio.CancelledError:
            if is_paper and commit_started and job_id is not None:
                raise QueueSubmissionCancelledError(job_id) from None
            raise
        except Exception:
            if is_paper and commit_started and job_id is not None:
                raise QueueSubmissionError(job_id) from None
            raise

        # Push to Redis queue
        try:
            r = await self._get_redis()
            await r.rpush(self.queue_key, job_id)
        except asyncio.CancelledError:
            if is_paper:
                raise QueueSubmissionCancelledError(job_id) from None
            raise
        except Exception:
            if is_paper:
                try:
                    async with db_session.session_manager.session() as session:
                        service = IngestionService(session)
                        await service.mark_failed(
                            job_id, "The job could not be queued. Retry the stored upload."
                        )
                        await session.commit()
                except Exception:  # noqa: BLE001 - retain persisted ownership on storage failure
                    logger.warning("Persisted job publication status unavailable: %s", job_id)
                raise QueueSubmissionError(job_id) from None
            if (meta or {}).get("workflow"):
                async with db_session.session_manager.session() as session:
                    service = IngestionService(session)
                    await service.mark_failed(
                        job_id, "The job could not be queued. Retry the stored upload."
                    )
                    await session.commit()
            raise
        logger.info("Enqueued job %s to Redis for file %s", job_id, file_path)
        return job_id

    async def requeue(self, job_id: str) -> None:
        """Re-enqueue an already authorized persisted job without creating a new row."""
        r = await self._get_redis()
        await r.rpush(self.queue_key, job_id)

    async def start_worker(self) -> None:
        """Start concurrent worker coroutines."""
        if self.is_running:
            return
        self.is_running = True

        for i in range(self.concurrency):
            task = asyncio.create_task(self._worker(worker_id=i), name=f"redis-worker-{i}")
            self._worker_tasks.append(task)

        logger.info(
            "Started %d Redis workers (GPU semaphore=%d)",
            self.concurrency,
            self.gpu_semaphore_limit,
        )

    async def stop_worker(self) -> None:
        """Stop all worker coroutines gracefully."""
        self.is_running = False
        for task in self._worker_tasks:
            task.cancel()
        for task in self._worker_tasks:
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._worker_tasks.clear()

        if self._redis:
            await self._redis.aclose()
            self._redis = None

        logger.info("All Redis workers stopped")

    async def get_queue_depth(self) -> int:
        """Return the number of jobs waiting in the queue."""
        r = await self._get_redis()
        return await r.llen(self.queue_key)

    async def get_dlq_depth(self) -> int:
        """Return the number of jobs in the dead letter queue."""
        r = await self._get_redis()
        return await r.llen(self.dlq_key)

    async def _worker(self, worker_id: int = 0) -> None:
        """Worker loop — pops jobs from Redis and processes them.

        Uses BLPOP with a 1-second timeout to allow graceful shutdown.
        On failure, applies exponential backoff and retries up to
        MAX_RETRIES before moving the job to the dead letter queue.
        """
        logger.info("Worker %d started", worker_id)

        while self.is_running:
            try:
                r = await self._get_redis()

                # Blocking pop with 1s timeout (allows shutdown check)
                result = await r.blpop(self.queue_key, timeout=1)
                if result is None:
                    continue  # Timeout, check is_running and loop

                _, job_id = result
                await self._process_job(job_id, worker_id)

            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Worker %d loop error", worker_id)
                await asyncio.sleep(1)

    async def _process_job(self, job_id: str, worker_id: int) -> None:
        """Process a consumed job and recover PAPER ownership during graceful cancellation."""
        try:
            await self._run_job(job_id, worker_id)
        except asyncio.CancelledError as error:
            await recover_interrupted_workflow(
                job_id,
                self.requeue,
                service_factory=IngestionService,
                **(
                    {"usage": error.usage_summary}
                    if isinstance(error, ExtractionCancelledError)
                    else {}
                ),
            )
            raise

    async def _run_job(self, job_id: str, worker_id: int) -> None:
        """Process a single job with retry logic.

        Args:
            job_id: The job to process.
            worker_id: Worker identifier for logging.
        """
        if db_session.session_manager is None:
            logger.error("DatabaseSessionManager is None in worker %d!", worker_id)
            return

        # Fetch job details
        async with db_session.session_manager.session() as session:
            service = IngestionService(session)
            job = await service.update_status(job_id, IngestionStatus.PROCESSING)
            await session.commit()
            file_path = job.file_path
            tenant_id = job.tenant_id
            meta = job.meta or {}
            model_id = meta.get("model_id", "qwen2-vl-2b-instruct")
            api_keys = meta.get("api_keys")
            start_page = meta.get("start_page")
            end_page = meta.get("end_page")

        result = None
        try:
            file_path = str(await resolve_upload_path(file_path))
            logger.info("Worker %d processing job %s: %s", worker_id, job_id, file_path)

            # GPU semaphore gates inference concurrency
            async with self._gpu_semaphore:
                workflow = meta.get("workflow")
                if workflow:
                    handler = self.workflow_handlers.get(workflow)
                    if handler is None:
                        raise ValueError("Queued workflow is unavailable.")
                    result = await handler(file_path, dict(meta))
                else:
                    import inspect

                    sig = inspect.signature(self.processing_function)
                    kwargs: dict[str, Any] = {}
                    if "api_keys" in sig.parameters:
                        kwargs["api_keys"] = api_keys
                    if "start_page" in sig.parameters:
                        kwargs["start_page"] = start_page
                    if "end_page" in sig.parameters:
                        kwargs["end_page"] = end_page

                    result = await self.processing_function(file_path, model_id, **kwargs)

            # Success — persist result
            async with db_session.session_manager.session() as session:
                service = IngestionService(session)
                await service.mark_completed(
                    job_id,
                    (
                        result.get("job_metadata", {})
                        if workflow
                        else {"result_summary": str(result)[:200] + "..."}
                    ),
                )
                doc_service = DocumentService(session)
                await doc_service.create_document(
                    job_id=job_id,
                    filename=meta.get("original_filename") or Path(file_path).name,
                    content=result,
                    tenant_id=tenant_id,
                )
                if isinstance(result, QueuedWorkflowResult):
                    result.release_artifact()
                await session.commit()

            # Clear retry counter on success
            try:
                r = await self._get_redis()
                await r.delete(f"{self.retry_key_prefix}{job_id}")
            except Exception:  # noqa: BLE001 - completion cannot fail on best-effort cleanup
                # Completion is already committed. Housekeeping cannot turn it
                # back into a failed/pending job or trigger another inference.
                logger.warning("Completed job retry counter cleanup failed: %s", job_id)

            logger.info("Worker %d completed job %s", worker_id, job_id)

        except asyncio.CancelledError as error:
            usage = error.usage_summary if isinstance(error, ExtractionCancelledError) else None
            if isinstance(result, QueuedWorkflowResult):
                usage = usage or result.recorded_usage
                await result.discard_uncommitted_artifact()
            if usage is not None:
                raise ExtractionCancelledError(usage) from None
            raise
        except Exception as e:
            usage = e.usage_summary if isinstance(e, ExtractionError) else None
            if usage is None and isinstance(result, QueuedWorkflowResult):
                usage = result.recorded_usage
            if isinstance(result, QueuedWorkflowResult):
                await result.discard_uncommitted_artifact()
            logger.exception("Worker %d failed job %s", worker_id, job_id)
            if meta.get("workflow"):
                if usage is not None:
                    await self._handle_failure(
                        job_id, str(e), workflow=meta["workflow"], usage=usage
                    )
                else:
                    await self._handle_failure(job_id, str(e), workflow=meta["workflow"])
            else:
                await self._handle_failure(job_id, str(e))

    async def _handle_failure(
        self,
        job_id: str,
        error_msg: str,
        *,
        workflow: str | None = None,
        usage: ExtractionUsage | None = None,
    ) -> None:
        """Handle job failure with exponential backoff and dead letter queue.

        Args:
            job_id: The failed job.
            error_msg: Error message to record.
        """
        # Persist paid-call diagnostics before any retry delay or Redis I/O.
        # Cancellation during backoff can then recover/requeue without losing
        # the attempt that already completed; the next run resumes this ledger.
        if usage is not None and db_session.session_manager is not None:
            async with db_session.session_manager.session() as session:
                await IngestionService(session).update_status(
                    job_id,
                    IngestionStatus.PROCESSING,
                    {"usage": usage.model_dump(mode="json")},
                )
                await session.commit()
        r = await self._get_redis()
        retry_key = f"{self.retry_key_prefix}{job_id}"

        # Increment retry count
        retry_count = await r.incr(retry_key)

        if retry_count > MAX_RETRIES:
            # Move to dead letter queue
            logger.warning(
                "Job %s exceeded %d retries, moving to DLQ",
                job_id,
                MAX_RETRIES,
            )
            await r.rpush(
                self.dlq_key,
                json.dumps({"job_id": job_id, "error": error_msg, "retries": retry_count}),
            )
            await r.delete(retry_key)

            # Mark as permanently failed in DB
            if db_session.session_manager:
                async with db_session.session_manager.session() as session:
                    service = IngestionService(session)
                    await service.mark_failed(
                        job_id,
                        f"Exceeded {MAX_RETRIES} retries: {error_msg}",
                        **({"usage": usage} if usage is not None else {}),
                    )
                    await session.commit()
        else:
            # Exponential backoff
            backoff = min(
                INITIAL_BACKOFF_S * (BACKOFF_MULTIPLIER ** (retry_count - 1)),
                MAX_BACKOFF_S,
            )
            logger.info(
                "Job %s retry %d/%d, backoff %.1fs",
                job_id,
                retry_count,
                MAX_RETRIES,
                backoff,
            )
            await asyncio.sleep(backoff)

            # Persist retry state before publishing the ID: another worker may
            # consume it immediately and must not have PROCESSING overwritten.
            if db_session.session_manager:
                async with db_session.session_manager.session() as session:
                    service = IngestionService(session)
                    if workflow:
                        await service.update_status(
                            job_id,
                            IngestionStatus.PENDING,
                            {
                                "retry_count": retry_count,
                                **({"usage": usage.model_dump(mode="json")} if usage else {}),
                            },
                        )
                    else:
                        await service.mark_failed(
                            job_id, f"Retry {retry_count}/{MAX_RETRIES}: {error_msg}"
                        )
                    await session.commit()

            await r.rpush(self.queue_key, job_id)
