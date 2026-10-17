"""Multimodal field routing and portable structured generation contracts."""

import json
from typing import Any
from unittest.mock import AsyncMock

import pytest

from src.extraction.contracts import (
    DocumentResult,
    ExternalSchema,
    ImageAsset,
    ModelDescriptor,
    ModelResponse,
    PageContent,
    TextBlock,
)
from src.extraction.errors import ExtractionError
from src.extraction.service import ExtractionService
from src.extraction.settings import ExtractionSettings


def page(
    number: int, text: str, *, preview: bool = True, descriptions: tuple[str, ...] = ()
) -> PageContent:
    images = tuple(
        ImageAsset(
            asset_id=f"p{number}-image-{i}",
            page_number=number,
            data_base64="cG5n",
            description=description,
        )
        for i, description in enumerate(descriptions, 1)
    )
    if preview:
        images += (
            ImageAsset(
                asset_id=f"p{number}-page", page_number=number, data_base64="cG5n", kind="page"
            ),
        )
    return PageContent(
        page_number=number,
        width=200,
        height=300,
        text_blocks=(
            (TextBlock(block_id=f"p{number}-text", page_number=number, text=text),) if text else ()
        ),
        images=images,
    )


def setup(
    pages: list[PageContent], outputs: list[str], **features: Any
) -> tuple[ExtractionService, AsyncMock, DocumentResult]:
    document = DocumentResult(
        document_id="pdf",
        source_name="source.pdf",
        content_mode="multimodal",
        text="\n".join(block.text for p in pages for block in p.text_blocks),
        pages=tuple(pages),
    )
    gateway = AsyncMock()
    gateway.describe = lambda profile: ModelDescriptor(model_id="fake", **features)
    gateway.generate.side_effect = [
        ModelResponse(content=output, model_id="fake") for output in outputs
    ]
    return ExtractionService(reader=AsyncMock(), gateway=gateway), gateway, document


def schema() -> ExternalSchema:
    return ExternalSchema(
        json_schema={
            "type": "object",
            "properties": {"po": {"type": "string"}},
            "required": ["po"],
            "additionalProperties": False,
        }
    )


def output(value: str, source: str) -> str:
    return json.dumps(
        {
            "data": {"po": value},
            "evidence": [{"field_path": "/po", "source_ids": [source], "quote": value}],
        }
    )


@pytest.mark.asyncio
async def test_native_json_field_schema_contains_generation_envelope() -> None:
    service, gateway, doc = setup(
        [page(1, "PO-1", preview=False)], [output("PO-1", "p1-text")], supports_native_json=True
    )
    await service.extract_fields(doc, schema())
    request = gateway.generate.await_args.args[1]
    assert request.json_schema["required"] == ["data", "evidence"]
    assert "required" not in request.json_schema["properties"]["data"]
    assert request.json_schema["properties"]["data"]["properties"]["po"]["type"] == "string"


@pytest.mark.asyncio
async def test_multimodal_fields_use_each_page_preview_with_max_images_one() -> None:
    service, gateway, doc = setup(
        [page(1, "Invoice header", descriptions=("Logo",)), page(2, "PO-2")],
        ['{"data":{},"evidence":[]}', output("PO-2", "p2-text")],
        supports_images=True,
        max_images=1,
    )
    result = await service.extract_fields(doc, schema())
    calls = [call.args[1] for call in gateway.generate.await_args_list]
    assert [request.images[0].asset_id for request in calls] == ["p1-page", "p2-page"]
    assert all(len(request.images) <= 1 for request in calls)
    assert result.data == {"po": "PO-2"}


@pytest.mark.asyncio
async def test_text_model_reads_asset_description_with_verifiable_evidence() -> None:
    service, gateway, doc = setup(
        [page(1, "", preview=False, descriptions=("PO-3",))],
        [output("PO-3", "p1-image-1")],
        supports_images=False,
    )
    result = await service.extract_fields(doc, schema())
    assert result.status == "succeeded"
    assert result.evidence[0].source_ids == ("p1-image-1",)
    assert not gateway.generate.await_args.args[1].images


@pytest.mark.asyncio
async def test_cropped_assets_without_preview_are_split_without_image_omission() -> None:
    service, gateway, doc = setup(
        [page(1, "", preview=False, descriptions=("PO-4", "Other details"))],
        [output("PO-4", "p1-image-1"), '{"data":{},"evidence":[]}'],
        supports_images=True,
        max_images=1,
    )
    result = await service.extract_fields(doc, schema())
    calls = [call.args[1] for call in gateway.generate.await_args_list]
    assert [image.asset_id for request in calls for image in request.images] == [
        "p1-image-1",
        "p1-image-2",
    ]
    assert result.data == {"po": "PO-4"}


@pytest.mark.asyncio
async def test_page_without_ocr_evidence_is_explicit_partial_result() -> None:
    service, gateway, doc = setup(
        [page(1, "PO-5"), page(2, "")],
        [output("PO-5", "p1-text"), '{"data":{},"evidence":[]}'],
        supports_images=True,
        max_images=1,
    )
    result = await service.extract_fields(doc, schema())
    assert result.status == "partial"
    assert any(warning.code == "image_evidence_unavailable" for warning in result.warnings)
    assert gateway.generate.await_args_list[-1].args[1].images[0].asset_id == "p2-page"


@pytest.mark.parametrize("number", ["NaN", "Infinity", "-Infinity", "1e999"])
@pytest.mark.asyncio
async def test_nonfinite_json_is_rejected_even_if_schema_allows_number(number: str) -> None:
    definition = ExternalSchema(
        json_schema={
            "type": "object",
            "properties": {"amount": {"type": "number"}},
            "required": ["amount"],
        }
    )
    model_output = '{"data":{"amount":' + number + '},"evidence":[]}'
    service, _, doc = setup([page(1, "Amount")], [model_output] * 2)
    with pytest.raises(ExtractionError) as caught:
        await service.extract_fields(doc, definition)
    assert caught.value.code == "schema_validation_failed"
    assert caught.value.__suppress_context__


@pytest.mark.asyncio
async def test_partial_schema_preserves_business_property_named_required() -> None:
    definition = ExternalSchema(
        json_schema={
            "type": "object",
            "properties": {"required": {"type": "string"}},
            "required": ["required"],
            "additionalProperties": False,
        }
    )
    model_output = json.dumps(
        {
            "data": {"required": "yes"},
            "evidence": [{"field_path": "/required", "source_ids": ["p1-text"], "quote": "yes"}],
        }
    )
    service, _, doc = setup([page(1, "yes", preview=False)], [model_output])
    result = await service.extract_fields(doc, definition)
    assert result.data == {"required": "yes"}


@pytest.mark.asyncio
async def test_repeated_line_items_are_preserved_and_evidence_indices_rebased() -> None:
    definition = ExternalSchema(
        json_schema={
            "type": "object",
            "properties": {
                "lines": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {"sku": {"type": "string"}},
                        "required": ["sku"],
                    },
                }
            },
            "required": ["lines"],
        }
    )

    def line_output(source: str) -> str:
        return json.dumps(
            {
                "data": {"lines": [{"sku": "SKU-A"}]},
                "evidence": [
                    {"field_path": "/lines/0/sku", "source_ids": [source], "quote": "SKU-A"}
                ],
            }
        )

    service, _, doc = setup(
        [page(1, "SKU-A"), page(2, "SKU-A")],
        [line_output("p1-text"), line_output("p2-text")],
        supports_images=True,
        max_images=1,
    )
    result = await service.extract_fields(doc, definition)
    assert result.data == {"lines": [{"sku": "SKU-A"}, {"sku": "SKU-A"}]}
    assert [item.field_path for item in result.evidence] == ["/lines/0/sku", "/lines/1/sku"]
    assert result.status == "succeeded"


@pytest.mark.asyncio
async def test_unreadable_image_only_document_fails_with_ocr_guidance() -> None:
    service, gateway, doc = setup([page(1, "")], [], supports_images=True)
    with pytest.raises(ExtractionError) as caught:
        await service.extract_fields(doc, schema())
    assert caught.value.code == "no_source_text"
    gateway.generate.assert_not_awaited()


@pytest.mark.asyncio
async def test_malformed_code_fence_is_a_typed_sanitized_failure() -> None:
    service, _, doc = setup([page(1, "PO-1")], ['```{"data":{}}```'] * 2)
    with pytest.raises(ExtractionError) as caught:
        await service.extract_fields(doc, schema())
    assert caught.value.code == "schema_validation_failed"


@pytest.mark.asyncio
async def test_text_only_provider_receives_explicit_portable_evidence_array_protocol() -> None:
    service, gateway, doc = setup([page(1, "PO-1", preview=False)], [output("PO-1", "p1-text")])
    await service.extract_fields(doc, schema())
    request = gateway.generate.await_args.args[1]
    assert request.json_schema is None
    assert '"evidence" must be a JSON array' in request.prompt
    assert '"data": {}, "evidence": []' in request.prompt
    assert '"source_ids"' in request.prompt
    assert '"field_path"' in request.prompt
    assert '"quote"' in request.prompt
    assert "literal" in request.prompt


@pytest.mark.asyncio
async def test_evidence_object_is_rejected_and_does_not_relax_response_contract() -> None:
    malformed = json.dumps({"data": {"po": "PO-1"}, "evidence": {"po": {"quote": "PO-1"}}})
    service, gateway, doc = setup([page(1, "PO-1")], [malformed] * 2)
    with pytest.raises(ExtractionError) as caught:
        await service.extract_fields(doc, schema())
    assert caught.value.code == "schema_validation_failed"
    assert gateway.generate.await_count == 2


@pytest.mark.asyncio
async def test_host_prompt_customization_retains_portable_response_protocol() -> None:
    _, gateway, doc = setup([page(1, "PO-1", preview=False)], [output("PO-1", "p1-text")])
    service = ExtractionService(
        reader=AsyncMock(),
        gateway=gateway,
        settings=ExtractionSettings(fields_prompt="Host extraction guidance."),
    )
    await service.extract_fields(doc, schema())
    request = gateway.generate.await_args.args[1]
    assert request.prompt.startswith("Host extraction guidance.")
    assert '"evidence" must be a JSON array' in request.prompt
