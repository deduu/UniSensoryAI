import asyncio
import re
import time
import logging
from pathlib import Path
from typing import Optional, Callable, Awaitable, Any

# Import module to allow late binding of session_manager
import src.db.session as db_session
from ..services.ingestion import IngestionService
from ..services.document import DocumentService
from ..db.models.ingestion import IngestionStatus

logger = logging.getLogger(__name__)

_UUID_PREFIX = re.compile(
    r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}_',
    re.IGNORECASE,
)

def _strip_uuid_prefix(filename: str) -> str:
    """Remove a leading UUID prefix (e.g. ``<uuid>_original.pdf``) from a filename."""
    return _UUID_PREFIX.sub('', filename)


class RateLimiter:
    """
    Token bucket rate limiter.
    """

    def __init__(self, rate_limit: float, capacity: float):
        self.rate_limit = rate_limit
        self.capacity = capacity
        self.tokens = capacity
        self.last_update = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self, tokens: float = 1.0):
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self.last_update
            self.last_update = now

            # Refill tokens
            new_tokens = elapsed * self.rate_limit
            self.tokens = min(self.capacity, self.tokens + new_tokens)

            if self.tokens < tokens:
                wait_time = (tokens - self.tokens) / self.rate_limit
                logger.debug(f"Rate limited, waiting {wait_time:.3f}s")
                await asyncio.sleep(wait_time)
                self.tokens = 0
            else:
                self.tokens -= tokens


class IngestionQueue:
    def __init__(self, processing_function: Callable[[str, str], Awaitable[Any]]):
        self.queue: asyncio.Queue = asyncio.Queue()
        self.processing_function = processing_function
        self.is_running = False
        self.worker_task: Optional[asyncio.Task] = None
        # Rate limiter: 10 req/s, burst of 10
        self.outbound_limiter = RateLimiter(rate_limit=10.0, capacity=10.0)

    async def enqueue(
        self,
        file_path: str,
        meta: Optional[dict] = None,
        *,
        tenant_id: str,
    ) -> str:
        """
        Create a job record and enqueue the file path.
        Returns the job_id.
        """
        if db_session.session_manager is None:
            raise RuntimeError("DatabaseSessionManager is not initialized! Call init_db first.")

        # Create database record
        async with db_session.session_manager.session() as session:
            service = IngestionService(session)
            job = await service.create_job(file_path, meta, tenant_id=tenant_id)
            job_id = job.id
            await session.commit()

        # Add to memory queue
        await self.queue.put(job_id)
        logger.info(f"Enqueued job {job_id} for file {file_path}")
        return job_id

    async def start_worker(self):
        if self.is_running:
            return
        self.is_running = True
        self.worker_task = asyncio.create_task(self._worker())
        logger.info("Ingestion worker started")

    async def stop_worker(self):
        self.is_running = False
        if self.worker_task:
            self.worker_task.cancel()
            try:
                await self.worker_task
            except asyncio.CancelledError:
                pass
        logger.info("Ingestion worker stopped")

    async def _worker(self):
        while self.is_running:
            try:
                job_id = await self.queue.get()

                if db_session.session_manager is None:
                    logger.error("DatabaseSessionManager is None in worker loop!")
                    # Put back? or fail?
                    self.queue.task_done()  # Mark done to avoid block, effectively dropping job (safest for now)
                    continue

                async with db_session.session_manager.session() as session:
                    service = IngestionService(session)

                    # Update status to PROCESSING
                    job = await service.update_status(job_id, IngestionStatus.PROCESSING)
                    await session.commit()
                    file_path = job.file_path
                    tenant_id = job.tenant_id
                    model_id = (job.meta or {}).get("model_id", "qwen2-vl-2b-instruct")
                    api_keys = (job.meta or {}).get("api_keys", None)
                    start_page = (job.meta or {}).get("start_page", None)
                    end_page = (job.meta or {}).get("end_page", None)

                try:
                    # Apply rate limit before processing (assuming processing makes outbound calls)
                    await self.outbound_limiter.acquire()

                    # Process
                    # NOTE: This is where we call the actual document agent/pipeline
                    logger.info(f"Processing job {job_id}: {file_path} with model {model_id}")
                    
                    import inspect
                    sig = inspect.signature(self.processing_function)
                    kwargs = {}
                    if "api_keys" in sig.parameters:
                        kwargs["api_keys"] = api_keys
                    if "start_page" in sig.parameters:
                        kwargs["start_page"] = start_page
                    if "end_page" in sig.parameters:
                        kwargs["end_page"] = end_page
                    result = await self.processing_function(file_path, model_id, **kwargs)

                    async with db_session.session_manager.session() as session:
                        # 1. Update IngestionJob status
                        service = IngestionService(session)
                        await service.mark_completed(
                            job_id, {"result_summary": str(result)[:200] + "..."}
                        )

                        # 2. Create Document record
                        doc_service = DocumentService(session)
                        # Use original_filename from meta (set at upload time).
                        # Fall back to stripping the UUID prefix from the stored path name
                        # for jobs submitted before this change.
                        raw_name = Path(file_path).name
                        display_name = (job.meta or {}).get("original_filename") or _strip_uuid_prefix(raw_name)
                        await doc_service.create_document(
                            job_id=job_id,
                            filename=display_name,
                            content=result,
                            tenant_id=tenant_id,
                        )

                        await session.commit()

                except Exception as e:
                    logger.error(f"Error processing job {job_id}: {e}", exc_info=True)
                    async with db_session.session_manager.session() as session:
                        service = IngestionService(session)
                        await service.mark_failed(job_id, str(e))
                        await session.commit()
                finally:
                    self.queue.task_done()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Worker loop error: {e}", exc_info=True)
                await asyncio.sleep(1)  # Prevent tight loop on error


# Global instance integration helper
_ingestion_queue: Optional[IngestionQueue] = None


def get_ingestion_queue() -> IngestionQueue:
    if _ingestion_queue is None:
        raise RuntimeError("Ingestion queue not initialized")
    return _ingestion_queue


def init_ingestion_queue(
    processing_func: Callable[[str, str], Awaitable[Any]],
    backend: Optional[str] = None,
    **kwargs,
) -> IngestionQueue:
    """Factory function to create the appropriate queue backend.

    Args:
        processing_func: The document processing function.
        backend: Queue backend — "redis" or "memory". Defaults to
            QUEUE_BACKEND env var, falling back to "memory".
        **kwargs: Additional kwargs passed to the queue constructor
            (e.g. redis_url, concurrency, gpu_semaphore_limit).

    Returns:
        An IngestionQueue (memory) or RedisIngestionQueue instance.
    """
    import os
    if backend is None:
        backend = os.getenv("QUEUE_BACKEND", "memory")

    global _ingestion_queue

    if backend == "redis":
        from src.ingestion.redis_queue import RedisIngestionQueue

        redis_url = kwargs.pop("redis_url", os.getenv("REDIS_URL", "redis://localhost:6379"))
        concurrency = kwargs.pop("concurrency", int(os.getenv("WORKER_CONCURRENCY", "4")))
        gpu_limit = kwargs.pop("gpu_semaphore_limit", int(os.getenv("GPU_SEMAPHORE_LIMIT", "1")))

        _ingestion_queue = RedisIngestionQueue(
            processing_function=processing_func,
            redis_url=redis_url,
            concurrency=concurrency,
            gpu_semaphore_limit=gpu_limit,
            **kwargs,
        )
        logger.info(
            "Initialized Redis queue (url=%s, concurrency=%d, gpu_limit=%d)",
            redis_url,
            concurrency,
            gpu_limit,
        )
    else:
        _ingestion_queue = IngestionQueue(processing_func)
        logger.info("Initialized in-memory queue")

    return _ingestion_queue

