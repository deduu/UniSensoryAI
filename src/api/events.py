"""Server-Sent Events (SSE) for real-time job status updates.

Provides an endpoint that streams job status changes until the job
completes or fails.

Usage::

    @app.get("/v1/jobs/{job_id}/stream")
    async def stream_job(job_id: str):
        return StreamingResponse(
            job_status_stream(job_id, db_session),
            media_type="text/event-stream",
        )
"""

import asyncio
import json
import logging
from typing import AsyncGenerator, Optional

logger = logging.getLogger(__name__)


async def job_status_stream(
    job_id: str,
    poll_interval_s: float = 1.0,
    timeout_s: float = 300.0,
) -> AsyncGenerator[str, None]:
    """Generate SSE events for a job's status changes.

    Polls the database at ``poll_interval_s`` intervals and emits
    an SSE event whenever the status changes. Terminates when the
    job reaches a terminal state (COMPLETED, FAILED) or timeout.

    Args:
        job_id: Job identifier.
        poll_interval_s: Polling interval in seconds.
        timeout_s: Maximum stream duration in seconds.

    Yields:
        SSE-formatted strings ("data: {...}\\n\\n").
    """
    import time

    import src.db.session as db_session
    from src.db.models.ingestion import IngestionStatus
    from src.services.ingestion import IngestionService

    terminal_statuses = {IngestionStatus.COMPLETED, IngestionStatus.FAILED}
    last_status = None
    start_time = time.monotonic()

    while time.monotonic() - start_time < timeout_s:
        try:
            if db_session.session_manager is None:
                yield _sse_event({"error": "Database not initialized"})
                return

            async with db_session.session_manager.session() as session:
                service = IngestionService(session)
                job = await service.get_by_id(job_id, raise_not_found=False)

                if job is None:
                    yield _sse_event({"error": f"Job {job_id} not found"})
                    return

                current_status = job.status

                if current_status != last_status:
                    event_data = {
                        "job_id": job_id,
                        "status": current_status.value,
                        "updated_at": str(job.updated_at) if job.updated_at else None,
                    }

                    # Include result info on completion
                    if current_status == IngestionStatus.COMPLETED:
                        event_data["documents"] = len(job.documents) if job.documents else 0

                    # Include error info on failure
                    if current_status == IngestionStatus.FAILED and job.meta:
                        event_data["error"] = job.meta.get("error", "Unknown error")

                    yield _sse_event(event_data)
                    last_status = current_status

                if current_status in terminal_statuses:
                    return

        except Exception as e:
            logger.error("SSE stream error for job %s: %s", job_id, e)
            yield _sse_event({"error": str(e)})
            return

        await asyncio.sleep(poll_interval_s)

    # Timeout
    yield _sse_event({"error": "Stream timeout", "job_id": job_id})


def _sse_event(data: dict) -> str:
    """Format a dict as an SSE event string.

    Args:
        data: Event data to serialize as JSON.

    Returns:
        SSE-formatted string.
    """
    return f"data: {json.dumps(data)}\n\n"
