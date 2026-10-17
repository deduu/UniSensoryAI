"""Model-selected span IDs resolve only to exact original document substrings."""

import json
from typing import Any
from unittest.mock import AsyncMock

import pytest
from jsonschema import Draft202012Validator

from src.extraction.contracts import (
    DocumentResult,
    ExternalSchema,
    ModelDescriptor,
    ModelRequest,
    ModelResponse,
    PageContent,
    TextBlock,
)
from src.extraction.service import ExtractionService


def _setup(
    text: str, *, limit: int = 48000
) -> tuple[ExtractionService, AsyncMock, DocumentResult, ExternalSchema]:
    document = DocumentResult(
        document_id="original-hash",
        source_name="source.pdf",
        content_mode="text",
        text=text,
        pages=(
            PageContent(
                page_number=1,
                width=100,
                height=100,
                text_blocks=(TextBlock(block_id="original-block", page_number=1, text=text),),
            ),
        ),
    )
    schema = ExternalSchema(
        json_schema={
            "type": "object",
            "properties": {"terms": {"type": "string"}},
            "additionalProperties": False,
        }
    )
    gateway = AsyncMock()
    gateway.describe = lambda profile: ModelDescriptor(
        model_id="host", supports_native_json=True, max_input_chars=limit
    )
    return ExtractionService(reader=AsyncMock(), gateway=gateway), gateway, document, schema


def _spans(request: ModelRequest) -> list[dict[str, str]]:
    return json.loads(request.prompt.split("\nSource spans:\n", 1)[1])


@pytest.mark.asyncio
async def test_span_selection_preserves_unicode_whitespace_and_exact_original_block_ids() -> None:
    text = "\u03b1\n" + "x" * 1010 + "  Both signatures AND complete documents.\r\n" + "y" * 1300
    service, gateway, document, schema = _setup(text)
    captured: list[dict[str, str]] = []

    async def respond(profile: str, request: ModelRequest) -> ModelResponse:
        if "Source spans:" not in request.prompt:
            return ModelResponse(
                content='{"data":{"terms":"Both prerequisites"},"evidence":[]}', model_id="host"
            )
        spans = _spans(request)
        captured.extend(spans)
        payload = {
            "evidence": [{"field_path": "/terms", "span_ids": [span["span_id"] for span in spans]}]
        }
        Draft202012Validator(request.json_schema).validate(payload)
        return ModelResponse(content=json.dumps(payload), model_id="host")

    gateway.generate.side_effect = respond
    result = await service.extract_fields(document, schema)
    assert captured, "Evidence repair must offer deterministic source spans"
    assert "".join(span["text"] for span in captured) == text
    assert all(len(span["text"]) <= 1200 for span in captured)
    assert all(len(span["text"]) >= 800 for span in captured[:-1])
    assert len({span["span_id"] for span in captured}) == len(captured)
    assert result.data == {"terms": "Both prerequisites"}
    assert [item.quote for item in result.evidence] == [span["text"] for span in captured]
    assert all(
        item.quote in text and item.source_ids == ("original-block",) for item in result.evidence
    )
    assert result.status == "succeeded"
    first_ids = [span["span_id"] for span in captured]
    captured.clear()
    await service.extract_fields(document, schema)
    assert [span["span_id"] for span in captured] == first_ids


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "invalid",
    [
        {"field_path": "/terms", "span_ids": ["invented"]},
        {"field_path": "/other", "span_ids": ["known"]},
        {"field_path": "/terms", "span_ids": ["known"], "quote": "invented"},
        {"field_path": "/terms", "span_ids": ["known"] * 17},
    ],
)
async def test_invalid_span_selection_is_rejected_without_mutating_values(
    invalid: dict[str, Any],
) -> None:
    service, gateway, document, schema = _setup("Original source clause")

    async def respond(profile: str, request: ModelRequest) -> ModelResponse:
        if "Source spans:" not in request.prompt:
            payload = {"data": {"terms": "Frozen candidate"}, "evidence": []}
        else:
            span_id = _spans(request)[0]["span_id"]
            item = {
                **invalid,
                "span_ids": [
                    span_id if identity == "known" else identity for identity in invalid["span_ids"]
                ],
            }
            payload = {"evidence": [item]}
        return ModelResponse(content=json.dumps(payload), model_id="host")

    gateway.generate.side_effect = respond
    result = await service.extract_fields(document, schema)
    assert result.data == {"terms": "Frozen candidate"}
    assert result.status == "partial"
    assert not result.evidence
    assert [issue.code for issue in result.warnings] == ["missing_evidence"]
    assert gateway.generate.await_count == 3


@pytest.mark.asyncio
async def test_span_repair_repackages_original_blocks_without_losing_extraction_chunk_boundaries() -> (
    None
):
    text = "source " * 1300 + "LAST CLAUSE"
    service, gateway, document, schema = _setup(text, limit=5000)
    visited: dict[str, str] = {}

    async def respond(profile: str, request: ModelRequest) -> ModelResponse:
        assert len(request.prompt) <= 5000
        if "Source spans:" not in request.prompt:
            payload = {"data": {"terms": "Last clause"}, "evidence": []}
        else:
            spans = _spans(request)
            visited.update({span["span_id"]: span["text"] for span in spans})
            payload = {
                "evidence": [
                    {"field_path": "/terms", "span_ids": [span["span_id"]]}
                    for span in spans
                    if "LAST CLAUSE" in span["text"]
                ]
            }
        return ModelResponse(content=json.dumps(payload), model_id="host")

    gateway.generate.side_effect = respond
    result = await service.extract_fields(document, schema)
    assert visited
    assert "".join(visited.values()) == text
    assert result.status == "succeeded"
    assert result.evidence[0].quote.endswith("LAST CLAUSE")
    assert result.evidence[0].source_ids == ("original-block",)
