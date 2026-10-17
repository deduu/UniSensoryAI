"""Persist model usage without attributing old uploads to today's deployment."""

from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.db.models.ingestion import IngestionStatus
from src.extraction.contracts import DocumentResult, FieldExtractionResult
from src.extraction.errors import ExtractionError
from src.paper.extraction_contracts import PaperExtractionResult
from src.services.paper_extraction import PaperExtractionProcessor
from src.services.paper_extraction_history import PaperExtractionHistoryService


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("ocr_models", "field_models", "expected"),
    [
        (("ocr",), ("fields", "ocr"), ["ocr", "fields"]),
        (("shared",), ("shared",), ["shared"]),
        ((), (), []),
        (("ocr",), None, ["ocr"]),
    ],
)
async def test_paper_completion_persists_only_recorded_unique_model_ids(
    ocr_models: tuple[str, ...],
    field_models: tuple[str, ...] | None,
    expected: list[str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("UPLOADS_DIR", str(tmp_path))
    source = tmp_path / "source.pdf"
    source.write_bytes(b"%PDF-1.7")
    document = DocumentResult(
        document_id="source",
        source_name="invoice.pdf",
        content_mode="text",
        text="Invoice",
        pages=(),
        model_ids=ocr_models,
    )
    fields = (
        None
        if field_models is None
        else FieldExtractionResult(
            schema_id="paper.rent_invoice", schema_version="1", data={}, model_ids=field_models
        )
    )
    field_extraction = AsyncMock(return_value=fields)
    if fields is None:
        field_extraction.side_effect = ExtractionError("provider_error", "Private provider values")
    service = SimpleNamespace(
        extract_document=AsyncMock(return_value=document), extract_fields=field_extraction
    )
    output = await PaperExtractionProcessor(AsyncMock(return_value=service)).process(
        str(source),
        {"schema_name": "rent_invoice", "original_filename": "invoice.pdf", "file_size": 8},
    )
    assert output["job_metadata"]["model_ids"] == expected
    if len(expected) == 1:
        assert output["job_metadata"]["model_id"] == expected[0]
    else:
        assert "model_id" not in output["job_metadata"]
    artifact = tmp_path / output["chunks"][0]["artifact_name"]
    restored = PaperExtractionResult.model_validate_json(artifact.read_text(encoding="utf-8"))
    assert restored.document.model_ids == ocr_models
    assert (restored.fields.model_ids if restored.fields is not None else None) == field_models
    assert "Private provider values" not in str(output["job_metadata"])


@pytest.mark.asyncio
@pytest.mark.parametrize("model_ids", [None, [], ["ocr", "fields"]])
async def test_paper_history_reports_usage_availability_from_persisted_metadata(
    model_ids: list[str] | None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("EXTRACTION_MODEL", "unrelated-current-model")
    metadata = {
        "workflow": "paper_extraction",
        "schema_name": "rent_invoice",
        "content_mode": "text",
        "original_filename": "invoice.pdf",
        "file_size": 42,
    }
    if model_ids is not None:
        metadata["model_ids"] = model_ids
    job = SimpleNamespace(
        id="job",
        status=IngestionStatus.COMPLETED,
        meta=metadata,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        documents=[],
    )
    result = MagicMock()
    result.scalars.return_value.all.return_value = [job]
    history = PaperExtractionHistoryService(AsyncMock(execute=AsyncMock(return_value=result)))
    listing = await history.list_jobs("tenant")
    history.find_job = AsyncMock(return_value=job)
    detail = await history.read_job("job", "tenant")
    for projected in (listing[0], detail):
        assert projected.model_ids == tuple(model_ids or [])
        assert projected.model_usage_recorded is (model_ids is not None)
        assert projected.file_size == 42
        assert "unrelated-current-model" not in projected.model_dump_json()
