"""Public extraction behavior with host-defined schemas and fake model ports."""

import asyncio
import json
from collections.abc import Sequence
from unittest.mock import AsyncMock

import pytest
from pydantic import BaseModel, field_validator

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
from src.extraction.errors import ExtractionError
from src.extraction.service import ExtractionService


def document(*texts: str, images: tuple[ImageAsset, ...] = ()) -> DocumentResult:
    pages = tuple(
        PageContent(
            page_number=i,
            width=200,
            height=300,
            text_blocks=(TextBlock(block_id=f"p{i}b0", page_number=i, text=text),),
            images=images if i == 1 else (),
        )
        for i, text in enumerate(texts, 1)
    )
    return DocumentResult(
        document_id="doc",
        source_name="source.pdf",
        content_mode="multimodal",
        text="\n".join(texts),
        pages=pages,
    )


def service_with(
    doc: DocumentResult, responses: Sequence[str] = (), max_input_chars: int = 48000
) -> tuple[ExtractionService, AsyncMock, AsyncMock]:
    reader = AsyncMock()
    reader.read.return_value = doc
    gateway = AsyncMock()
    gateway.describe = lambda profile: ModelDescriptor(
        model_id="fake", supports_images=True, max_input_chars=max_input_chars
    )
    gateway.generate.side_effect = [
        ModelResponse(content=value, model_id="fake") for value in responses
    ]
    return ExtractionService(reader=reader, gateway=gateway), reader, gateway


@pytest.mark.asyncio
async def test_native_text_uses_no_model_and_does_not_replace_source() -> None:
    source = document("PO-123", "All remaining text")
    service, _reader, gateway = service_with(source)
    result = await service.extract_document(
        PdfSource(data=b"%PDF"), ExtractionOptions(text_strategy="native_only")
    )
    assert "PO-123" in result.text and "All remaining text" in result.text
    assert result.page_count == 2
    assert result.content_mode == "text"
    gateway.generate.assert_not_awaited()


@pytest.mark.asyncio
async def test_text_only_can_ocr_scans_but_does_not_return_images() -> None:
    image = ImageAsset(asset_id="p1-page", page_number=1, kind="page", data_base64="aGVsbG8=")
    source = document("", images=(image,))
    source = source.model_copy(
        update={"pages": (source.pages[0].model_copy(update={"is_scanned": True}),)}
    )
    service, _, gateway = service_with(source, ["Scanned PO-123"])
    result = await service.extract_document(PdfSource(data=b"%PDF"))
    assert result.text == "Scanned PO-123"
    assert result.pages[0].images == ()
    assert result.pages[0].text_blocks[0].origin == "ocr"
    assert gateway.generate.await_args.args[1].images


@pytest.mark.asyncio
async def test_multimodal_keeps_images_and_native_text_without_ocr_when_requested() -> None:
    image = ImageAsset(asset_id="p1-image", page_number=1, data_base64="aGVsbG8=")
    service, _, gateway = service_with(document("Embedded text", images=(image,)))
    result = await service.extract_document(
        PdfSource(data=b"%PDF"),
        ExtractionOptions(content_mode="multimodal", text_strategy="native_only"),
    )
    assert result.pages[0].images[0].asset_id == "p1-image"
    assert result.text == "Embedded text"
    assert (
        json.loads(result.model_dump_json())["pages"][0]["images"][0]["data_base64"] == "aGVsbG8="
    )
    gateway.generate.assert_not_awaited()


def po_schema() -> ExternalSchema:
    return ExternalSchema(
        schema_id="reconciliation.po",
        json_schema={
            "type": "object",
            "properties": {"po_number": {"type": "string"}},
            "required": ["po_number"],
            "additionalProperties": False,
        },
    )


@pytest.mark.asyncio
async def test_external_business_schema_and_evidence_are_separate() -> None:
    response = json.dumps(
        {
            "data": {"po_number": "PO-123"},
            "evidence": [{"field_path": "/po_number", "source_ids": ["p1b0"], "quote": "PO-123"}],
        }
    )
    service, _, gateway = service_with(document("Purchase order PO-123"), [response])
    result = await service.extract_fields(document("Purchase order PO-123"), po_schema())
    assert result.data == {"po_number": "PO-123"}
    assert result.evidence[0].source_ids == ("p1b0",)
    assert result.schema_id == "reconciliation.po"
    assert result.status == "succeeded"
    assert "po_number" in gateway.generate.await_args.args[1].prompt


@pytest.mark.asyncio
async def test_missing_source_evidence_is_explicit_partial_result() -> None:
    service, _, _ = service_with(
        document("PO-123"), ['{"data":{"po_number":"PO-123"},"evidence":[]}']
    )
    result = await service.extract_fields(document("PO-123"), po_schema())
    assert result.status == "partial"
    assert result.warnings[0].code == "missing_evidence"


@pytest.mark.asyncio
async def test_fabricated_evidence_is_not_returned_as_grounded() -> None:
    response = json.dumps(
        {
            "data": {"po_number": "PO-123"},
            "evidence": [
                {"field_path": "/po_number", "source_ids": ["nonexistent"], "quote": "invented"}
            ],
        }
    )
    service, _, _ = service_with(document("PO-123"), [response])
    result = await service.extract_fields(document("PO-123"), po_schema())
    assert not result.evidence and result.status == "partial"


@pytest.mark.asyncio
async def test_invalid_model_json_or_schema_never_becomes_success() -> None:
    service, _, _ = service_with(document("PO-123"), ['{"data":{},"evidence":[]}'] * 2)
    with pytest.raises(ExtractionError) as error:
        await service.extract_fields(document("PO-123"), po_schema())
    assert error.value.code == "schema_validation_failed"
    assert "PO-123" not in str(error.value)


@pytest.mark.asyncio
async def test_pydantic_business_validators_are_enforced() -> None:
    class RequiredPrefix(BaseModel):
        po_number: str

        @field_validator("po_number")
        @classmethod
        def check_prefix(cls, value: str) -> str:
            if not value.startswith("PO-"):
                raise ValueError("Invalid order")
            return value

    service, _, _ = service_with(
        document("bad"), ['{"data":{"po_number":"bad"},"evidence":[]}'] * 2
    )
    with pytest.raises(ExtractionError):
        await service.extract_fields(document("bad"), RequiredPrefix)


@pytest.mark.asyncio
async def test_whole_document_is_chunked_without_dropping_later_pages() -> None:
    source = document("a " * 3000, "PO-999")
    responses = [
        '{"data":{},"evidence":[]}',
        json.dumps(
            {
                "data": {"po_number": "PO-999"},
                "evidence": [
                    {"field_path": "/po_number", "source_ids": ["p2b0"], "quote": "PO-999"}
                ],
            }
        ),
    ]
    service, _, gateway = service_with(source, responses, max_input_chars=6000)
    result = await service.extract_fields(source, po_schema())
    assert result.data["po_number"] == "PO-999"
    prompts = [call.args[1].prompt for call in gateway.generate.await_args_list]
    assert len(prompts) >= 2
    assert all(len(prompt) <= 6000 for prompt in prompts)
    assert "PO-999" in prompts[-1]


@pytest.mark.asyncio
async def test_conflicting_scalar_candidates_fail_explicitly() -> None:
    source = document("a " * 3000, "PO-999")
    service, _, _ = service_with(
        source,
        [
            '{"data":{"po_number":"PO-123"},"evidence":[]}',
            '{"data":{"po_number":"PO-999"},"evidence":[]}',
        ],
        max_input_chars=6000,
    )
    with pytest.raises(ExtractionError) as error:
        await service.extract_fields(source, po_schema())
    assert error.value.code == "conflicting_fields"


@pytest.mark.asyncio
async def test_combined_extraction_calls_reader_once() -> None:
    service, reader, _ = service_with(
        document("PO-123"), ['{"data":{"po_number":"PO-123"},"evidence":[]}']
    )
    result = await service.extract(
        PdfSource(data=b"%PDF"),
        schema=po_schema(),
        options=ExtractionOptions(text_strategy="native_only"),
    )
    assert result.fields.data["po_number"] == "PO-123"
    assert result.document.text == "PO-123"
    reader.read.assert_awaited_once()


@pytest.mark.asyncio
async def test_cancellation_propagates() -> None:
    service, _, gateway = service_with(document("PO-123"))
    gateway.generate.side_effect = asyncio.CancelledError
    with pytest.raises(asyncio.CancelledError):
        await service.extract_fields(document("PO-123"), po_schema())
