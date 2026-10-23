"""Source index backfill is scoped, opt-in, additive and keeps history timestamps."""

from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.sql.dml import Update

from src.db.models.document import Document
from src.db.models.ingestion import IngestionJob
from src.paper.workspace.backfill_query import SourceIdentityBackfillQuery
from src.services.paper_source_identity_backfill import backfill_source_identities
from tests.unit.test_paper_extraction_source_lookup import (
    NOW,
    OTHER_ID,
    SOURCE_ID,
    _database,
    _store,
)


@pytest.mark.asyncio
async def test_dry_run_has_no_writes_and_apply_preserves_all_other_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("UPLOADS_DIR", str(tmp_path))
    async with _database() as db:
        await _store(db, tmp_path, "legacy", SOURCE_ID)
        await db.commit()
        job = await db.scalar(select(IngestionJob).where(IngestionJob.id == "legacy"))
        before = dict(job.meta)
        report = await backfill_source_identities(
            db, SourceIdentityBackfillQuery(tenant_id="tenant-a", job_id="legacy")
        )
        assert report.candidates == {"legacy": SOURCE_ID}
        assert report.updated_job_ids == ()
        await db.refresh(job)
        assert job.meta == before
        report = await backfill_source_identities(
            db, SourceIdentityBackfillQuery(tenant_id="tenant-a", job_id="legacy", apply=True)
        )
        assert report.updated_job_ids == ("legacy",)
        await db.commit()
        await db.refresh(job)
        assert job.meta == {**before, "document_id": SOURCE_ID}
        assert job.updated_at.replace(tzinfo=NOW.tzinfo) == NOW


@pytest.mark.asyncio
async def test_backfill_never_overwrites_existing_or_crosses_tenant(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("UPLOADS_DIR", str(tmp_path))
    async with _database() as db:
        await _store(db, tmp_path, "existing", SOURCE_ID, indexed_id=OTHER_ID)
        await _store(db, tmp_path, "private", SOURCE_ID, tenant_id="tenant-b")
        await _store(db, tmp_path, "corrupt", SOURCE_ID, corrupt=True)
        await db.commit()
        result = await backfill_source_identities(
            db, SourceIdentityBackfillQuery(tenant_id="tenant-a", apply=True)
        )
        assert result.updated_job_ids == ()
        assert result.skipped_existing_job_ids == ("existing",)
        assert result.unavailable_job_ids == ("corrupt",)
        assert result.scanned == 2
        hidden = await backfill_source_identities(
            db, SourceIdentityBackfillQuery(tenant_id="tenant-a", job_id="private", apply=True)
        )
        assert hidden.scanned == 0


@pytest.mark.asyncio
async def test_failed_apply_rolls_back_the_entire_batch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("UPLOADS_DIR", str(tmp_path))
    async with _database() as db:
        await _store(db, tmp_path, "first", SOURCE_ID)
        await _store(db, tmp_path, "second", OTHER_ID)
        await db.commit()
        original_execute = db.execute
        updates = 0

        async def fail_second(statement: object, *args: object, **kwargs: object) -> object:
            nonlocal updates
            if isinstance(statement, Update):
                updates += 1
                if updates == 2:
                    raise RuntimeError("Interrupted")
            return await original_execute(statement, *args, **kwargs)

        monkeypatch.setattr(db, "execute", fail_second)
        with pytest.raises(RuntimeError, match="Interrupted"):
            await backfill_source_identities(
                db, SourceIdentityBackfillQuery(tenant_id="tenant-a", apply=True)
            )
        monkeypatch.setattr(db, "execute", original_execute)
        metadata = (await db.scalars(select(IngestionJob.meta))).all()
        assert all((item or {}).get("document_id") is None for item in metadata)


@pytest.mark.asyncio
async def test_conflicting_artifacts_do_not_establish_source_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("UPLOADS_DIR", str(tmp_path))
    async with _database() as db:
        await _store(db, tmp_path, "legacy", SOURCE_ID)
        await _store(db, tmp_path, "different", OTHER_ID)
        db.add(
            Document(
                id="extra-artifact",
                tenant_id="tenant-a",
                job_id="legacy",
                filename="same-name.pdf",
                content_chunks=[
                    {
                        "type": "paper_extraction_artifact",
                        "artifact_name": "different.paper-extraction.json",
                    }
                ],
            )
        )
        await db.commit()
        result = await backfill_source_identities(
            db, SourceIdentityBackfillQuery(tenant_id="tenant-a", job_id="legacy", apply=True)
        )
        assert result.updated_job_ids == ()
        assert result.conflict_job_ids == ("legacy",)
        assert result.candidates == {}
