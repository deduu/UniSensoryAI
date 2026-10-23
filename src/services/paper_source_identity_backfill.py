"""Add missing canonical source metadata from validated tenant-owned artifacts only."""

import asyncio
from typing import Any, cast

from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.db.models.ingestion import IngestionJob, IngestionStatus
from src.paper.workspace.backfill_query import SourceIdentityBackfillQuery
from src.paper.workspace.backfill_result import SourceIdentityBackfillResult
from src.services.paper_extraction_history import _DOCUMENT_ID, _bounded_artifact_result
from src.services.upload_storage import resolve_upload_path


async def backfill_source_identities(
    db: AsyncSession, query: SourceIdentityBackfillQuery
) -> SourceIdentityBackfillResult:
    """Validate source artifacts before any optional metadata additions.

    Args:
        db: Injected host transaction; caller alone owns commit or rollback.
        query: Explicit tenant, optional exact job, batch bound and apply flag.

    Returns:
        Dry-run candidates or additive updates with exact skip dispositions.

    Raises:
        TimeoutError: The bounded storage and artifact work exceeds fifteen seconds.
    """
    validated = SourceIdentityBackfillQuery.model_validate(query)
    return await asyncio.wait_for(_transactional_backfill(db, validated), timeout=15)


async def _transactional_backfill(
    db: AsyncSession, query: SourceIdentityBackfillQuery
) -> SourceIdentityBackfillResult:
    if query.apply:
        async with db.begin_nested():
            return await _backfill(db, query)
    return await _backfill(db, query)


async def _backfill(
    db: AsyncSession, query: SourceIdentityBackfillQuery
) -> SourceIdentityBackfillResult:
    statement = (
        select(IngestionJob)
        .where(
            IngestionJob.tenant_id == query.tenant_id,
            IngestionJob.status == IngestionStatus.COMPLETED,
            IngestionJob.meta["workflow"].as_string() == "paper_extraction",
        )
        .options(selectinload(IngestionJob.documents))
        .order_by(IngestionJob.id)
        .limit(query.limit)
    )
    if query.job_id:
        statement = statement.where(IngestionJob.id == query.job_id)
    if query.apply:
        statement = statement.with_for_update()
    jobs = (await db.scalars(statement)).all()
    candidates: dict[str, str] = {}
    existing: list[str] = []
    conflicts: list[str] = []
    unavailable: list[str] = []
    metadata: dict[str, dict[str, Any]] = {}
    for job in jobs:
        meta = dict(job.meta or {})
        if meta.get("document_id") is not None:
            existing.append(job.id)
            continue
        artifacts = [
            chunk.get("artifact_name")
            for document in job.documents
            if document.tenant_id == query.tenant_id and document.job_id == job.id
            for chunk in document.content_chunks or ()
            if isinstance(chunk, dict) and chunk.get("type") == "paper_extraction_artifact"
        ]
        if not artifacts or len(artifacts) > 100:
            unavailable.append(job.id)
            continue
        identities: set[str] = set()
        try:
            for artifact_name in artifacts:
                if not isinstance(artifact_name, str):
                    raise TypeError("Artifact reference is invalid.")
                path = await resolve_upload_path(artifact_name)
                extracted = await asyncio.to_thread(_bounded_artifact_result, path)
                identities.add(_DOCUMENT_ID.validate_python(extracted.document.document_id))
        except (OSError, TypeError, ValueError):
            unavailable.append(job.id)
            continue
        if len(identities) != 1:
            conflicts.append(job.id)
            continue
        candidates[job.id] = identities.pop()
        metadata[job.id] = meta
    # Every candidate has now been validated in scope. Hold the job lock when
    # applying, never replace an existing identity and keep chronology unchanged.
    updated: list[str] = []
    if query.apply:
        for job_id, document_id in candidates.items():
            result = cast(
                CursorResult[Any],
                await db.execute(
                    update(IngestionJob)
                    .where(
                        IngestionJob.id == job_id,
                        IngestionJob.tenant_id == query.tenant_id,
                        IngestionJob.meta["document_id"].as_string().is_(None),
                    )
                    .values(
                        meta={**metadata[job_id], "document_id": document_id},
                        updated_at=IngestionJob.updated_at,
                    )
                    .execution_options(synchronize_session=False)
                ),
            )
            if result.rowcount == 1:
                updated.append(job_id)
            else:
                conflicts.append(job_id)
    return SourceIdentityBackfillResult(
        dry_run=not query.apply,
        scanned=len(jobs),
        candidates=candidates,
        updated_job_ids=tuple(updated),
        skipped_existing_job_ids=tuple(existing),
        conflict_job_ids=tuple(conflicts),
        unavailable_job_ids=tuple(unavailable),
    )
