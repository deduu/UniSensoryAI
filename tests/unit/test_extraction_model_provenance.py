"""Model history records completed generation responses rather than current bindings."""

import json
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from src.extraction.contracts import (
    DocumentResult,
    ExternalSchema,
    ExtractionOptions,
    ImageAsset,
    ModelDescriptor,
    ModelResponse,
    PageContent,
    PdfSource,
    TextBlock,
)
from src.extraction.service import ExtractionService
from src.extraction.settings import ExtractionSettings


def _document(*, scanned: bool = False) -> DocumentResult:
    return DocumentResult(
        document_id="source",
        source_name="source.pdf",
        content_mode="text",
        text="PO-123",
        pages=(
            PageContent(
                page_number=1,
                width=100,
                height=100,
                is_scanned=scanned,
                text_blocks=(
                    ()
                    if scanned
                    else (TextBlock(block_id="source-block", page_number=1, text="PO-123"),)
                ),
                images=(
                    tuple(
                        ImageAsset(
                            asset_id=f"page-{index}",
                            page_number=1,
                            kind="page",
                            data_base64="aW1hZ2U=",
                        )
                        for index in range(3)
                    )
                    if scanned
                    else ()
                ),
            ),
        ),
    )


def _schema() -> ExternalSchema:
    return ExternalSchema(
        json_schema={
            "type": "object",
            "properties": {"number": {"type": "string"}},
            "required": ["number"],
            "additionalProperties": False,
        }
    )


def _service(
    document: DocumentResult, responses: list[ModelResponse], *, focused: bool = False
) -> ExtractionService:
    reader = AsyncMock()
    reader.read.return_value = document
    gateway = AsyncMock()
    gateway.describe = lambda profile: ModelDescriptor(model_id="current-config-is-not-history")
    gateway.generate.side_effect = responses
    return ExtractionService(
        reader=reader,
        gateway=gateway,
        settings=ExtractionSettings(field_review_batch_size=1 if focused else 0),
    )


@pytest.mark.asyncio
async def test_native_text_records_no_model_and_old_artifacts_remain_readable() -> None:
    source = _document()
    result = await _service(source, []).extract_document(
        PdfSource(data=b"%PDF"), ExtractionOptions(text_strategy="native_only")
    )
    assert result.model_ids == ()
    payload = source.model_dump(exclude={"model_ids"})
    assert DocumentResult.model_validate(payload).model_ids == ()


@pytest.mark.asyncio
async def test_ocr_records_response_model_ids_once_in_first_use_order() -> None:
    result = await _service(
        _document(scanned=True),
        [ModelResponse(content="PO-123", model_id=model) for model in ("ocr-a", "ocr-b", "ocr-a")],
    ).extract_document(PdfSource(data=b"%PDF"))
    assert result.model_ids == ("ocr-a", "ocr-b")
    assert json.loads(result.model_dump_json())["model_ids"] == ["ocr-a", "ocr-b"]


@pytest.mark.asyncio
async def test_empty_provider_model_ids_do_not_become_recorded_usage() -> None:
    result = await _service(
        _document(scanned=True),
        [ModelResponse(content="PO-123", model_id=model) for model in ("", " ", "ocr")],
    ).extract_document(PdfSource(data=b"%PDF"))
    assert result.model_ids == ("ocr",)


def test_document_model_usage_rejects_empty_identifiers() -> None:
    with pytest.raises(ValidationError):
        DocumentResult.model_validate({**_document().model_dump(), "model_ids": [""]})


@pytest.mark.asyncio
async def test_fields_keep_retry_selection_review_and_repair_model_ids_through_validation() -> None:
    responses = [
        ModelResponse(content="not JSON", model_id="initial"),
        ModelResponse(content='{"data":{"number":"PO-123"},"evidence":[]}', model_id="retry"),
        ModelResponse(content='{"source_ids":["source-block"]}', model_id="selector"),
        ModelResponse(content='{"data":{"number":"PO-123"},"evidence":[]}', model_id="review"),
        ModelResponse(
            content=json.dumps(
                {
                    "evidence": [
                        {
                            "field_path": "/number",
                            "source_ids": ["source-block"],
                            "quote": "PO-123",
                        }
                    ]
                }
            ),
            model_id="repair",
        ),
    ]
    result = await _service(_document(), responses, focused=True).extract_fields(
        _document(), _schema()
    )
    assert result.model_ids == ("initial", "retry", "selector", "review", "repair")
    assert result.data == {"number": "PO-123"}
    assert result.evidence[0].quote == "PO-123"
