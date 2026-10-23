"""Additive queued PDF upload, persisted history, and original-file retrieval."""

import asyncio
import shutil
from collections.abc import AsyncIterator, Callable, Iterator
from contextlib import contextmanager
from functools import partial
from pathlib import Path
from typing import Annotated, Literal
from uuid import uuid4

import fastapi
import structlog
from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
)
from fastapi.responses import FileResponse, Response
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth import UserContext, get_user_context
from src.api.extraction_routes import _read_upload, _SafeValidationRoute
from src.api.rate_limit import InProcessRateLimiter, RateLimitDep
from src.db.models.ingestion import IngestionStatus
from src.db.session import get_db
from src.extraction.contracts import ExtractionOptions
from src.ingestion.queue_manager import get_ingestion_queue
from src.ingestion.submission_cancelled_error import QueueSubmissionCancelledError
from src.ingestion.submission_error import QueueSubmissionError
from src.paper.extraction_archive_error import PaperExtractionArchiveError
from src.paper.extraction_contracts import (
    ExtractionArchiveRequest,
    PaperExtractionJob,
    PaperExtractionParameters,
)
from src.services.base_pdf_page_preview import BasePdfPagePreview
from src.services.paper_extraction_history import PaperExtractionHistoryService
from src.services.pdf_page_preview import PdfPagePreviewService
from src.services.upload_storage import get_upload_directory, resolve_upload_path

logger = structlog.get_logger(__name__)
_limiter = InProcessRateLimiter(requests_per_minute=6000, burst=100)
_rate_limit = RateLimitDep(requests_per_minute=6000, limiter=_limiter)
router = APIRouter(
    prefix="/v1/paper/extractions",
    tags=["paper extraction"],
    route_class=_SafeValidationRoute,
    dependencies=[Depends(_rate_limit)],
)
JobId = Annotated[str, fastapi.Path(min_length=1, max_length=50, pattern=r"^[A-Za-z0-9-]+$")]
DocumentId = Annotated[
    str, fastapi.Path(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
]
PageNumber = Annotated[int, fastapi.Path(ge=1, le=500)]


def _not_found() -> HTTPException:
    return HTTPException(
        status_code=404, detail={"code": "not_found", "message": "Extraction was not found."}
    )


@contextmanager
def _storage_errors() -> Iterator[None]:
    try:
        yield
    except (SQLAlchemyError, asyncio.TimeoutError):
        raise HTTPException(
            status_code=503,
            detail={
                "code": "storage_unavailable",
                "message": "Extraction history storage is unavailable.",
            },
        ) from None
    except (OSError, ValueError):
        raise HTTPException(
            status_code=503,
            detail={
                "code": "artifact_unavailable",
                "message": "Stored extraction output is unavailable.",
            },
        ) from None


async def _db_session() -> AsyncIterator[AsyncSession]:
    async for session in get_db():
        yield session


async def get_history_service(
    db: Annotated[AsyncSession, Depends(_db_session)],
) -> PaperExtractionHistoryService:
    """Inject a tenant-filtered repository over the host's existing job tables."""
    return PaperExtractionHistoryService(db)


def get_page_preview_service() -> BasePdfPagePreview:
    """Inject a model-free renderer for original-page human review.

    Returns:
        A replaceable bounded original-page preview service.
    """
    return PdfPagePreviewService()


def _write_upload(payload: bytes, root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    destination = root / f"{uuid4()}.pdf"
    try:
        destination.write_bytes(payload)
    except BaseException:
        destination.unlink(missing_ok=True)
        raise
    return destination


def _copy_upload(source: Path, root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    destination = root / f"{uuid4()}.pdf"
    try:
        shutil.copyfile(source, destination)
    except BaseException:
        destination.unlink(missing_ok=True)
        raise
    return destination


async def _remove_unowned_source(path: Path) -> None:
    try:
        await asyncio.to_thread(path.unlink, missing_ok=True)
    except OSError:
        logger.warning("paper_unowned_upload_cleanup_failed")


async def _store_new_source(write: Callable[[], Path]) -> Path:
    task = asyncio.create_task(asyncio.to_thread(write))
    try:
        return await asyncio.shield(task)
    except asyncio.CancelledError:
        # The physical write must finish before removing its unowned output.
        try:
            path = await asyncio.shield(task)
        except Exception:  # noqa: BLE001 - preserve the caller's cancellation
            logger.warning("paper_cancelled_source_write_failed")
        else:
            await _remove_unowned_source(path)
        raise


def _queue_unavailable() -> HTTPException:
    return HTTPException(
        status_code=503,
        detail={
            "code": "queue_unavailable",
            "message": "The extraction could not be queued. Check upload history before retrying.",
        },
    )


async def _enqueue_source(path: Path, parameters: PaperExtractionParameters, tenant_id: str) -> str:
    try:
        return await get_ingestion_queue().enqueue(
            str(path),
            meta=parameters.model_dump(mode="json", exclude_none=True),
            tenant_id=tenant_id,
        )
    except BaseException as error:
        if not isinstance(error, (QueueSubmissionError, QueueSubmissionCancelledError)):
            await _remove_unowned_source(path)
        if isinstance(error, Exception):
            raise _queue_unavailable() from None
        raise


@router.post(
    "", response_model=PaperExtractionJob, response_model_exclude_none=True, status_code=202
)
async def upload_extraction(
    file: Annotated[UploadFile, File()],
    user: Annotated[UserContext, Depends(get_user_context)],
    history: Annotated[PaperExtractionHistoryService, Depends(get_history_service)],
    schema_name: Annotated[Literal["rent_agreement", "rent_invoice"], Form()],
    content_mode: Annotated[Literal["text", "multimodal"], Form()] = "text",
) -> PaperExtractionJob:
    """Validate and queue a PDF; inference runs in existing background workers.

    Args:
        file: Original PDF, bounded by the same extraction upload limits.
        user: Authenticated tenant, never accepted from form fields.
        history: Shared database history adapter.
        schema_name: External canonical PAPER schema to apply after OCR.
        content_mode: Text-only or retained multimodal source representation.

    Returns:
        Persistent pending job metadata for polling and later reopening.
    """
    try:
        source = await _read_upload(file, ExtractionOptions(content_mode=content_mode))
        assert source.data is not None
        parameters = PaperExtractionParameters(
            schema_name=schema_name,
            content_mode=content_mode,
            original_filename=source.filename,
            file_size=len(source.data),
        )
        with _storage_errors():
            path = await _store_new_source(
                partial(_write_upload, source.data, get_upload_directory())
            )
            job_id = await _enqueue_source(path, parameters, user.tenant_id)
            job = await history.read_job(job_id, user.tenant_id)
        if job is None:
            raise _not_found()
        return job
    except HTTPException:
        raise
    except Exception:  # noqa: BLE001 - queue adapters must not expose connection credentials
        raise _queue_unavailable() from None
    finally:
        await file.close()


@router.get("", response_model=tuple[PaperExtractionJob, ...], response_model_exclude_none=True)
async def list_extractions(
    user: Annotated[UserContext, Depends(get_user_context)],
    history: Annotated[PaperExtractionHistoryService, Depends(get_history_service)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    archived: bool = False,
) -> tuple[PaperExtractionJob, ...]:
    """List active attempts by default, or explicitly list recoverable archived attempts."""
    with _storage_errors():
        return await history.list_jobs(
            user.tenant_id, limit=limit, offset=offset, archived=archived
        )


@router.post(
    "/archive", response_model=tuple[PaperExtractionJob, ...], response_model_exclude_none=True
)
async def archive_extractions(
    body: ExtractionArchiveRequest,
    user: Annotated[UserContext, Depends(get_user_context)],
    history: Annotated[PaperExtractionHistoryService, Depends(get_history_service)],
    db: Annotated[AsyncSession, Depends(_db_session)],
) -> tuple[PaperExtractionJob, ...]:
    """Archive or restore terminal attempts while retaining all source and audit data.

    Args:
        body: Explicit job targets and desired archive state; no tenant override.
        user: Authenticated tenant and actor used for every target and audit stamp.
        history: Existing extraction repository, retaining all original artifacts.
        db: Shared transaction committed only after the complete batch validates.

    Returns:
        Updated lightweight metadata, with archive and restore audit information.
    """
    with _storage_errors():
        try:
            result = await history.set_archived(body, user.tenant_id, user_id=user.user_id)
        except PaperExtractionArchiveError as error:
            raise HTTPException(
                status_code=404 if error.code == "not_found" else 409,
                detail={"code": error.code, "message": str(error)},
            ) from None
        await asyncio.wait_for(db.commit(), timeout=15)
        return result


@router.get("/by-document/{document_id}", response_model=PaperExtractionJob)
async def read_extraction_by_document(
    document_id: DocumentId,
    user: Annotated[UserContext, Depends(get_user_context)],
    history: Annotated[PaperExtractionHistoryService, Depends(get_history_service)],
) -> PaperExtractionJob:
    """Resolve an exact canonical document identity to its stored source extraction.

    Args:
        document_id: Canonical extraction identity, independent of job and DB IDs.
        user: Authenticated tenant, never accepted from request query fields.
        history: Tenant-scoped persisted extraction history adapter.

    Returns:
        Newest readable matching extraction with original content and citations.
    """
    with _storage_errors():
        result = await history.read_by_document(document_id, user.tenant_id)
    if result is None:
        raise _not_found()
    return result


@router.get("/{job_id}", response_model=PaperExtractionJob)
async def read_extraction(
    job_id: JobId,
    user: Annotated[UserContext, Depends(get_user_context)],
    history: Annotated[PaperExtractionHistoryService, Depends(get_history_service)],
) -> PaperExtractionJob:
    """Reopen a result with its original source IDs, evidence, and warnings."""
    with _storage_errors():
        result = await history.read_job(job_id, user.tenant_id, include_result=True)
    if result is None:
        raise _not_found()
    return result


@router.get("/{job_id}/file")
async def read_original(
    job_id: JobId,
    user: Annotated[UserContext, Depends(get_user_context)],
    history: Annotated[PaperExtractionHistoryService, Depends(get_history_service)],
) -> FileResponse:
    """Serve the original PDF only after tenant-scoped job authorization."""
    with _storage_errors():
        job = await history.find_job(job_id, user.tenant_id)
    if job is None:
        raise _not_found()
    try:
        path = await resolve_upload_path(job.file_path)
    except FileNotFoundError:
        raise _not_found() from None
    return FileResponse(
        path,
        media_type="application/pdf",
        filename=(job.meta or {}).get("original_filename", "document.pdf"),
        content_disposition_type="inline",
    )


@router.get("/{job_id}/pages/{page_number}")
async def read_original_page(
    job_id: JobId,
    page_number: PageNumber,
    user: Annotated[UserContext, Depends(get_user_context)],
    history: Annotated[PaperExtractionHistoryService, Depends(get_history_service)],
    preview: Annotated[BasePdfPagePreview, Depends(get_page_preview_service)],
) -> Response:
    """Render an authorized original page for side-by-side human inspection.

    Args:
        job_id: Persisted extraction job belonging to the current tenant.
        page_number: One-based original PDF page, bounded to 500 pages.
        user: Host-authenticated tenant context.
        history: Tenant-filtered shared history repository.
        preview: Host-injected model-free original-page renderer.

    Returns:
        Private, non-cacheable PNG bytes of the selected original page.
    """
    with _storage_errors():
        job = await history.find_job(job_id, user.tenant_id)
    if job is None:
        raise _not_found()
    with _storage_errors():
        try:
            source = await resolve_upload_path(job.file_path)
            content = await preview.render(source, page_number)
        except FileNotFoundError:
            raise _not_found() from None
    return Response(
        content,
        media_type="image/png",
        headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"},
    )


@router.post(
    "/{job_id}/retry",
    response_model=PaperExtractionJob,
    response_model_exclude_none=True,
    status_code=202,
)
async def retry_extraction(
    job_id: JobId,
    user: Annotated[UserContext, Depends(get_user_context)],
    history: Annotated[PaperExtractionHistoryService, Depends(get_history_service)],
) -> PaperExtractionJob:
    """Queue an independent copy of a failed source while keeping its old history."""
    with _storage_errors():
        original = await history.find_job(job_id, user.tenant_id)
    if original is None:
        raise _not_found()
    if original.status != IngestionStatus.FAILED:
        raise HTTPException(
            status_code=409,
            detail={"code": "invalid_status", "message": "Only failed extractions can be retried."},
        )
    with _storage_errors():
        source = await resolve_upload_path(original.file_path)
        metadata = original.meta or {}
        parameters = PaperExtractionParameters.model_validate(
            {
                key: metadata[key]
                for key in PaperExtractionParameters.model_fields
                if key in metadata
            }
        ).model_copy(update={"retry_of": job_id})
        target = await _store_new_source(partial(_copy_upload, source, get_upload_directory()))
        replacement_id = await _enqueue_source(target, parameters, user.tenant_id)
        replacement = await history.read_job(replacement_id, user.tenant_id)
    if replacement is None:
        raise _not_found()
    return replacement
