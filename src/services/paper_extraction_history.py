"""Tenant-scoped history over existing ingestion jobs and document storage."""

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Literal

from pydantic import StringConstraints, TypeAdapter
from sqlalchemy import Select, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.orm.attributes import set_committed_value

from src.db.models.ingestion import IngestionJob, IngestionStatus
from src.paper.extraction_archive_error import PaperExtractionArchiveError
from src.paper.extraction_contracts import (
    DocumentReuse,
    ExtractionArchiveRequest,
    PaperExtractionJob,
    PaperExtractionResult,
)
from src.services.upload_storage import resolve_upload_path

_STATUSES: dict[IngestionStatus, Literal["pending", "processing", "completed", "failed"]] = {
    IngestionStatus.PENDING: "pending",
    IngestionStatus.PROCESSING: "processing",
    IngestionStatus.COMPLETED: "completed",
    IngestionStatus.FAILED: "failed",
}
_DOCUMENT_ID: TypeAdapter[str] = TypeAdapter(
    Annotated[
        str,
        StringConstraints(
            strict=True, min_length=1, max_length=128, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$"
        ),
    ]
)
_LOOKUP_PAGE_SIZE = 50
_MAX_ARTIFACT_BYTES = 100 * 1024 * 1024
_ACTOR_ID: TypeAdapter[str] = TypeAdapter(
    Annotated[
        str, StringConstraints(strict=True, strip_whitespace=True, min_length=1, max_length=255)
    ]
)


def _bounded_artifact_result(path: Path) -> PaperExtractionResult:
    with path.open("rb") as artifact:
        payload = artifact.read(_MAX_ARTIFACT_BYTES + 1)
    if len(payload) > _MAX_ARTIFACT_BYTES:
        raise ValueError("Stored extraction exceeds the source lookup budget.")
    return PaperExtractionResult.model_validate_json(payload)


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
        self, tenant_id: str, *, limit: int = 50, offset: int = 0, archived: bool = False
    ) -> tuple[PaperExtractionJob, ...]:
        """List active or archived attempts without changing source-read availability.

        Args:
            tenant_id: Authenticated tenant scope.
            limit: Bounded page size supplied by the transport.
            offset: Number of attempts to skip within the chosen visibility state.
            archived: False for active history; True for recoverable archived attempts.

        Returns:
            Lightweight metadata without reading or deleting stored artifacts.
        """
        archived_flag = IngestionJob.meta["paper_archive"]["archived"].as_boolean()
        result = await asyncio.wait_for(
            self._db.execute(
                self._query(tenant_id)
                .where(archived_flag.is_(True) if archived else archived_flag.is_not(True))
                .order_by(IngestionJob.created_at.desc(), IngestionJob.id.desc())
                .limit(limit)
                .offset(offset)
            ),
            timeout=15,
        )
        return tuple(self._metadata(job) for job in result.scalars().all())

    async def set_archived(
        self, request: ExtractionArchiveRequest, tenant_id: str, *, user_id: str
    ) -> tuple[PaperExtractionJob, ...]:
        """Atomically archive or restore terminal attempts without owning the transaction.

        Args:
            request: Explicit validated job identifiers and desired visibility state.
            tenant_id: Trusted tenant scope, never accepted from archive request data.
            user_id: Trusted reviewer recorded against the archive or restore action.

        Returns:
            Metadata in requested order, retaining sources and processing timestamps.

        Raises:
            PaperExtractionArchiveError: Any target is unavailable or still active.
            TimeoutError: The complete storage operation exceeds fifteen seconds.
        """
        request = ExtractionArchiveRequest.model_validate(request)
        tenant_id = _ACTOR_ID.validate_python(tenant_id)
        user_id = _ACTOR_ID.validate_python(user_id)
        return await asyncio.wait_for(self._set_archived(request, tenant_id, user_id), timeout=15)

    async def _set_archived(
        self, request: ExtractionArchiveRequest, tenant_id: str, user_id: str
    ) -> tuple[PaperExtractionJob, ...]:
        async with self._db.begin_nested():
            result = await self._db.execute(
                self._query(tenant_id)
                .where(IngestionJob.id.in_(request.job_ids))
                .order_by(IngestionJob.id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            jobs = {job.id: job for job in result.scalars().all()}
            if len(jobs) != len(request.job_ids):
                raise PaperExtractionArchiveError(
                    "not_found", "One or more extraction attempts are unavailable."
                )
            if any(
                job.status in {IngestionStatus.PENDING, IngestionStatus.PROCESSING}
                for job in jobs.values()
            ):
                raise PaperExtractionArchiveError(
                    "active_extraction", "Wait for active extraction attempts to finish first."
                )
            now = datetime.now(timezone.utc).isoformat()
            for job_id in request.job_ids:
                job = jobs[job_id]
                metadata = dict(job.meta or {})
                state = metadata.get("paper_archive")
                state = dict(state) if isinstance(state, dict) else {}
                if (state.get("archived") is True) == request.archived:
                    continue
                action = "archived" if request.archived else "restored"
                metadata["paper_archive"] = {
                    **state,
                    "archived": request.archived,
                    f"{action}_at": now,
                    f"{action}_by": user_id,
                }
                await self._db.execute(
                    update(IngestionJob)
                    .where(IngestionJob.id == job.id, IngestionJob.tenant_id == tenant_id)
                    .values(meta=metadata, updated_at=IngestionJob.updated_at)
                    .execution_options(synchronize_session=False)
                )
                set_committed_value(job, "meta", metadata)
            return tuple(self._metadata(jobs[job_id]) for job_id in request.job_ids)

    async def read_by_document(self, document_id: str, tenant_id: str) -> PaperExtractionJob | None:
        """Find the newest readable source, including jobs predating identity metadata.

        Args:
            document_id: Validated canonical extraction identity, never a filename.
            tenant_id: Authenticated host tenant used to scope every candidate.

        Returns:
            Full exact matching extraction, or None when no readable match exists.

        Raises:
            ValidationError: The requested canonical identity is invalid.
            TimeoutError: The complete lookup exceeds its fifteen-second budget.
        """
        document_id = _DOCUMENT_ID.validate_python(document_id)
        return await asyncio.wait_for(self._find_document(document_id, tenant_id), timeout=15)

    async def _find_document(self, document_id: str, tenant_id: str) -> PaperExtractionJob | None:
        stored_id = IngestionJob.meta["document_id"].as_string()
        query = (
            self._query(tenant_id)
            .where(or_(stored_id == document_id, stored_id.is_(None)))
            .order_by(IngestionJob.created_at.desc(), IngestionJob.id.desc())
        )
        offset = 0
        while True:
            result = await self._db.execute(query.limit(_LOOKUP_PAGE_SIZE).offset(offset))
            jobs = result.scalars().all()
            for job in jobs:
                extracted = await self._matching_result(job, document_id, tenant_id)
                if extracted is not None:
                    return self._metadata(job, extracted)
            if len(jobs) < _LOOKUP_PAGE_SIZE:
                return None
            offset += len(jobs)

    async def _matching_result(
        self, job: IngestionJob, document_id: str, tenant_id: str
    ) -> PaperExtractionResult | None:
        for document in reversed(job.documents):
            if document.tenant_id != tenant_id:
                continue
            for chunk in document.content_chunks or []:
                if not isinstance(chunk, dict) or chunk.get("type") != "paper_extraction_artifact":
                    continue
                artifact_name = chunk.get("artifact_name")
                if not isinstance(artifact_name, str):
                    continue
                try:
                    artifact = await resolve_upload_path(artifact_name)
                    extracted = await asyncio.to_thread(_bounded_artifact_result, artifact)
                except (OSError, ValueError):
                    # A missing or invalid legacy artifact cannot establish identity.
                    continue
                if extracted.document.document_id == document_id:
                    return extracted
        return None

    def _metadata(
        self, job: IngestionJob, result: PaperExtractionResult | None = None
    ) -> PaperExtractionJob:
        meta = job.meta or {}
        archive = meta.get("paper_archive")
        archive = archive if isinstance(archive, dict) else {}
        reuse = meta.get("document_reuse")
        if isinstance(reuse, dict):
            # Stored private annotations predate this public contract. Project
            # only provenance fields; keep persisted metadata and input rules intact.
            reuse = {key: reuse[key] for key in DocumentReuse.model_fields if key in reuse}
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
            usage=meta.get("usage"),
            document_reuse=DocumentReuse.model_validate(reuse) if reuse is not None else None,
            file_size=meta.get("file_size"),
            page_count=meta.get("page_count"),
            warning_count=meta.get("warning_count", 0),
            extraction_status=meta.get("extraction_status"),
            archived=archive.get("archived") is True,
            archived_at=archive.get("archived_at"),
            archived_by=archive.get("archived_by"),
            restored_at=archive.get("restored_at"),
            restored_by=archive.get("restored_by"),
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
