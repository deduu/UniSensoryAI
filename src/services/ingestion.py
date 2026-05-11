from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy import select
from typing import Optional, Any, Sequence
from .base import BaseService
from ..db.models.ingestion import IngestionJob, IngestionStatus
import uuid

class IngestionService(BaseService[IngestionJob]):
    def __init__(self, db: AsyncSession):
        super().__init__(db, IngestionJob)

    async def get_by_id(
        self,
        item_id: Any,
        raise_not_found: bool = True,
        *,
        tenant_id: Optional[str] = None,
    ) -> Optional[IngestionJob]:
        stmt = select(self.model).where(self.model.id == item_id).options(selectinload(self.model.documents))
        if tenant_id is not None:
            stmt = stmt.where(self.model.tenant_id == tenant_id)
        result = await self.db.execute(stmt)
        obj = result.scalar_one_or_none()
        if not obj and raise_not_found:
             from .exceptions import NotFoundException
             raise NotFoundException(self.model.__name__, item_id)
        return obj

    async def create_job(
        self,
        file_path: str,
        meta: Optional[dict[str, Any]] = None,
        *,
        tenant_id: str,
    ) -> IngestionJob:
        job_id = str(uuid.uuid4())
        return await self.create(
            id=job_id,
            tenant_id=tenant_id,
            file_path=file_path,
            status=IngestionStatus.PENDING,
            meta=meta
        )

    async def update_status(self, job_id: str, status: IngestionStatus, meta_update: Optional[dict[str, Any]] = None) -> IngestionJob:
        # We need to fetch, then update to handle meta updates properly (merging or replacing)
        # For simple status updates, we could use update statement, but BaseService.update loads the object essentially.
        
        # If meta_update is provided, we merge it with existing meta
        update_data: dict[str, Any] = {"status": status}
        
        if meta_update:
            current_job = await self.get_by_id(job_id)
            if current_job: # Should exist, get_by_id checks by default
                current_meta = dict(current_job.meta) if current_job.meta else {}
                current_meta.update(meta_update)
                update_data["meta"] = current_meta

        return await self.update(job_id, **update_data)
        
    async def mark_failed(self, job_id: str, error: str) -> IngestionJob:
        return await self.update_status(job_id, IngestionStatus.FAILED, {"error": error})

    async def mark_completed(self, job_id: str, result_summary: Optional[dict[str, Any]] = None) -> IngestionJob:
        return await self.update_status(job_id, IngestionStatus.COMPLETED, result_summary)

    async def fail_interrupted_jobs(self, error: str = "interrupted by server restart") -> int:
        # The in-memory worker queue is lost on restart, so anything still in
        # PENDING or PROCESSING was orphaned. Mark them FAILED so the UI stops
        # spinning forever; users can re-upload deliberately.
        stmt = select(self.model).where(
            self.model.status.in_([IngestionStatus.PENDING, IngestionStatus.PROCESSING])
        )
        result = await self.db.execute(stmt)
        orphaned = result.scalars().all()
        for job in orphaned:
            job.status = IngestionStatus.FAILED
            meta = dict(job.meta) if job.meta else {}
            meta["error"] = error
            job.meta = meta
        await self.db.flush()
        return len(orphaned)

    async def list_jobs(
        self,
        limit: int = 50,
        offset: int = 0,
        *,
        tenant_id: Optional[str] = None,
    ) -> Sequence[IngestionJob]:
        stmt = (
            select(self.model)
            .options(selectinload(self.model.documents))
            .order_by(self.model.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        if tenant_id is not None:
            stmt = stmt.where(self.model.tenant_id == tenant_id)
        result = await self.db.execute(stmt)
        return result.scalars().all()
