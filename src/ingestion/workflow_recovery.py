"""Small interruption handoff for existing PAPER workers; no provider dependencies."""

import asyncio
from collections.abc import Awaitable, Callable

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

import src.db.session as db_session
from src.db.models.ingestion import IngestionStatus
from src.services.ingestion import IngestionService

logger = structlog.get_logger(__name__)


async def recover_interrupted_workflow(
    job_id: str,
    requeue: Callable[[str], Awaitable[None]],
    *,
    service_factory: Callable[[AsyncSession], IngestionService],
) -> None:
    """Commit a safe pending handoff, or retain an explicit failed interruption.

    Args:
        job_id: Persisted ID that the stopping worker had already consumed.
        requeue: Backend-specific publication operation, without creating another job.
        service_factory: Existing job service constructor injected for the host session.
    """
    manager = db_session.session_manager
    if manager is None:
        logger.warning("interrupted_workflow_storage_unavailable", job_id=job_id)
        return

    async def handoff() -> bool:
        async with manager.session() as session:
            service = service_factory(session)
            job = await service.get_by_id(job_id, raise_not_found=False)
            if (
                job is None
                or (job.meta or {}).get("workflow") != "paper_extraction"
                or job.status not in {IngestionStatus.PROCESSING, IngestionStatus.PENDING}
            ):
                return False
            await service.update_status(job_id, IngestionStatus.PENDING, {"interrupted": True})
            await session.commit()
        await requeue(job_id)
        return True

    try:
        await asyncio.wait_for(handoff(), timeout=10)
    except Exception:  # noqa: BLE001 - never expose backend connection information

        async def mark_interrupted() -> None:
            async with manager.session() as session:
                service = service_factory(session)
                job = await service.get_by_id(job_id, raise_not_found=False)
                if (
                    job is not None
                    and (job.meta or {}).get("workflow") == "paper_extraction"
                    and job.status in {IngestionStatus.PROCESSING, IngestionStatus.PENDING}
                ):
                    await service.mark_failed(
                        job_id,
                        "Processing was interrupted before completion. Retry the stored upload.",
                    )
                    await session.commit()

        try:
            await asyncio.wait_for(mark_interrupted(), timeout=10)
        except Exception:  # noqa: BLE001 - database can also be unavailable during shutdown
            logger.warning("interrupted_workflow_recovery_failed", job_id=job_id)
