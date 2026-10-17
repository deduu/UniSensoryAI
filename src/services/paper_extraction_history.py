"""Tenant-scoped history over existing ingestion jobs and document storage."""

import asyncio
from typing import Literal

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.db.models.ingestion import IngestionJob, IngestionStatus
from src.paper.extraction_contracts import PaperExtractionJob, PaperExtractionResult
from src.services.upload_storage import resolve_upload_path

_STATUSES: dict[IngestionStatus, Literal["pending", "processing", "completed", "failed"]] = {
    IngestionStatus.PENDING: "pending",
    IngestionStatus.PROCESSING: "processing",
    IngestionStatus.COMPLETED: "completed",
    IngestionStatus.FAILED: "failed",
}


class PaperExtractionHistoryService:
    """Load persisted upload history without coupling extraction to accounting approval."""

    def __init__(self, db: AsyncSession) -> None:
        """Inject the host's database session."""
        self._db = db

    def _query(self, tenant_id: str) -> Select[tuple[IngestionJob]]:
        return (
            select(IngestionJob)
            .where(
                IngestionJob.tenant_id == tenant_id,
                IngestionJob.meta["workflow"].as_string() == "paper_extraction",
            )
            .options(selectinload(IngestionJob.documents))
        )

    async def find_job(self, job_id: str, tenant_id: str) -> IngestionJob | None:
        """Return only an extraction owned by the authenticated tenant."""
        result = await asyncio.wait_for(
            self._db.execute(self._query(tenant_id).where(IngestionJob.id == job_id)), timeout=15
        )
        return result.scalar_one_or_none()

    async def list_jobs(
        self, tenant_id: str, *, limit: int = 50, offset: int = 0
    ) -> tuple[PaperExtractionJob, ...]:
        """Return lightweight most-recent-first metadata without reading heavy artifacts."""
        result = await asyncio.wait_for(
            self._db.execute(
                self._query(tenant_id)
                .order_by(IngestionJob.created_at.desc())
                .limit(limit)
                .offset(offset)
            ),
            timeout=15,
        )
        return tuple(self._metadata(job) for job in result.scalars().all())

    def _metadata(
        self, job: IngestionJob, result: PaperExtractionResult | None = None
    ) -> PaperExtractionJob:
        meta = job.meta or {}
        return PaperExtractionJob(
            job_id=job.id,
            filename=meta["original_filename"],
            schema_name=meta["schema_name"],
            content_mode=meta.get("content_mode", "text"),
            status=_STATUSES[job.status],
            created_at=job.created_at,
            updated_at=job.updated_at,
            model_ids=meta.get("model_ids", ()),
            model_usage_recorded="model_ids" in meta,
            file_size=meta.get("file_size"),
            page_count=meta.get("page_count"),
            warning_count=meta.get("warning_count", 0),
            extraction_status=meta.get("extraction_status"),
            error=(
                "Document extraction failed. Retry the upload or review its original PDF."
                if job.status.value == "FAILED"
                else None
            ),
            result=result,
        )

    async def read_job(
        self, job_id: str, tenant_id: str, *, include_result: bool = False
    ) -> PaperExtractionJob | None:
        """Reopen stored extraction including full evidence and warnings when requested."""
        job = await self.find_job(job_id, tenant_id)
        if job is None:
            return None
        extracted = None
        if include_result:
            for document in reversed(job.documents):
                if document.tenant_id != tenant_id:
                    continue
                for chunk in document.content_chunks or []:
                    if chunk.get("type") == "paper_extraction_artifact":
                        artifact = await resolve_upload_path(chunk["artifact_name"])
                        payload = await asyncio.to_thread(artifact.read_text, encoding="utf-8")
                        extracted = await asyncio.to_thread(
                            PaperExtractionResult.model_validate_json, payload
                        )
                        break
                if extracted is not None:
                    break
        return self._metadata(job, extracted)
