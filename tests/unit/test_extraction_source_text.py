"""Narrative review annotations never let citation repair replace business values."""

import json
from typing import Any
from unittest.mock import AsyncMock

import pytest

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
    properties: dict[str, Any], values: dict[str, Any], source: str
) -> tuple[ExtractionService, AsyncMock, DocumentResult, ExternalSchema]:
    document = DocumentResult(
        document_id="hash",
        source_name="source.pdf",
        content_mode="text",
        text=source,
        pages=(
            PageContent(
                page_number=1,
                width=100,
                height=100,
                text_blocks=(TextBlock(block_id="operative", page_number=1, text=source),),
            ),
        ),
    )
    schema = ExternalSchema(
        json_schema={"type": "object", "properties": properties, "additionalProperties": False}
    )
    gateway = AsyncMock()
    gateway.describe = lambda profile: ModelDescriptor(model_id="host")

    async def respond(profile: str, request: ModelRequest) -> ModelResponse:
        if "Source spans:" not in request.prompt:
            payload = {
                "data": values,
                "evidence": [
                    {"field_path": "/terms", "source_ids": ["operative"], "quote": source[:20]}
                ],
            }
        else:
            spans = json.loads(request.prompt.split("\nSource spans:\n", 1)[1])
            paths = list(
                json.loads(
                    request.prompt.split("\nRequested fields and immutable values:\n", 1)[1].split(
                        "\nSource spans:\n", 1
                    )[0]
                )
            )
            payload = {
                "evidence": [
                    {"field_path": path, "span_ids": [span["span_id"] for span in spans]}
                    for path in paths
                ]
            }
        return ModelResponse(content=json.dumps(payload), model_id="host")

    gateway.generate.side_effect = respond
    return ExtractionService(reader=AsyncMock(), gateway=gateway), gateway, document, schema


@pytest.mark.asyncio
async def test_annotated_narrative_preserves_candidate_and_requires_independent_review() -> None:
    source = "Rebuilding applies only after exceptional loss. Other termination requires separate agreement; damages apply solely to the specified breach."
    service, gateway, document, schema = _setup(
        {"terms": {"type": "string", "x-source-text": True}},
        {"terms": "All termination always requires damages"},
        source,
    )
    result = await service.extract_fields(document, schema)
    assert gateway.generate.await_count == 1
    assert result.data["terms"] == "All termination always requires damages"
    assert all(item.quote in source for item in result.evidence)
    assert any(issue.code == "source_text_review_required" for issue in result.warnings)
    assert not any(issue.code == "source_text_grounded" for issue in result.warnings)


@pytest.mark.asyncio
async def test_annotation_supports_string_array_leaves_and_preserves_unannotated_values() -> None:
    source = "Full operative condition AND an express exception."
    service, _, document, schema = _setup(
        {
            "terms": {"type": "array", "items": {"type": "string"}, "x-source-text": True},
            "summary": {"type": "string"},
        },
        {"terms": ["Shortened condition"], "summary": "Host summary"},
        source,
    )
    result = await service.extract_fields(document, schema)
    assert result.data == {"terms": ["Shortened condition"], "summary": "Host summary"}
    assert any(item.field_path == "/terms/0" for item in result.evidence)
    assert any(
        issue.field_path == "/terms/0" and issue.code == "source_text_review_required"
        for issue in result.warnings
    )


@pytest.mark.asyncio
async def test_annotated_excerpt_that_breaks_schema_limit_keeps_candidate_and_explicit_review_gap() -> (
    None
):
    source = "A complete source clause longer than the caller permits."
    service, _, document, schema = _setup(
        {"terms": {"type": "string", "maxLength": 12, "x-source-text": True}},
        {"terms": "Short"},
        source,
    )
    result = await service.extract_fields(document, schema)
    assert result.data == {"terms": "Short"}
    assert any(issue.code == "source_text_review_required" for issue in result.warnings)
    assert result.status == "partial"


@pytest.mark.asyncio
async def test_annotated_legacy_quote_without_selected_spans_remains_review_gap() -> None:
    source = "Complete condition AND exception."
    service, gateway, document, schema = _setup(
        {"terms": {"type": "string", "x-source-text": True}}, {"terms": "Paraphrase"}, source
    )
    gateway.generate.side_effect = [
        ModelResponse(content='{"data":{"terms":"Paraphrase"},"evidence":[]}', model_id="host"),
        ModelResponse(
            content=json.dumps(
                {
                    "evidence": [
                        {"field_path": "/terms", "source_ids": ["operative"], "quote": source}
                    ]
                }
            ),
            model_id="host",
        ),
        ModelResponse(content='{"evidence":[]}', model_id="host"),
    ]
    result = await service.extract_fields(document, schema)
    assert result.data == {"terms": "Paraphrase"}
    assert any(issue.code == "source_text_review_required" for issue in result.warnings)


@pytest.mark.asyncio
async def test_unannotated_schema_retains_existing_quote_based_workflow() -> None:
    source = "Original source clause."
    service, gateway, document, schema = _setup(
        {"terms": {"type": "string"}}, {"terms": "Summary"}, source
    )
    result = await service.extract_fields(document, schema)
    assert result.data["terms"] == "Summary"
    assert gateway.generate.await_count == 1
    assert not result.warnings


@pytest.mark.asyncio
async def test_repeated_selected_evidence_never_duplicates_text_into_narrative_value() -> None:
    repeated = "x" * 1000
    service, gateway, document, schema = _setup(
        {"terms": {"type": "string", "x-source-text": True}},
        {"terms": "Paraphrase"},
        repeated + repeated,
    )

    async def respond(profile: str, request: ModelRequest) -> ModelResponse:
        if "Source spans:" not in request.prompt:
            payload = {"data": {"terms": "Paraphrase"}, "evidence": []}
        else:
            spans = json.loads(request.prompt.split("\nSource spans:\n", 1)[1])
            payload = {"evidence": [{"field_path": "/terms", "span_ids": [spans[1]["span_id"]]}]}
        return ModelResponse(content=json.dumps(payload), model_id="host")

    gateway.generate.side_effect = respond
    result = await service.extract_fields(document, schema)
    assert result.data["terms"] == "Paraphrase"
    assert len(result.evidence) == 1
    assert result.evidence[0].quote == repeated
    assert any(issue.code == "source_text_review_required" for issue in result.warnings)


@pytest.mark.asyncio
async def test_mid_word_partial_span_preserves_complete_focused_payment_conditions() -> None:
    source = (
        "prefix " * 142
        + "installment amount 7190 requires both signatures; the next stage requires complete documents before the stated deadline. "
        + "context " * 150
    )
    candidate = "Stage one is 7190 after both signatures. The next stage requires complete documents before the stated deadline."
    service, gateway, document, schema = _setup(
        {"terms": {"type": "string", "x-source-text": True}}, {"terms": candidate}, source
    )
    selected: list[str] = []

    async def respond(profile: str, request: ModelRequest) -> ModelResponse:
        if "Source spans:" not in request.prompt:
            payload = {"data": {"terms": candidate}, "evidence": []}
        else:
            spans = json.loads(request.prompt.split("\nSource spans:\n", 1)[1])
            selected.append(spans[1]["text"])
            payload = {"evidence": [{"field_path": "/terms", "span_ids": [spans[1]["span_id"]]}]}
        return ModelResponse(content=json.dumps(payload), model_id="host")

    gateway.generate.side_effect = respond
    result = await service.extract_fields(document, schema)
    assert selected[0].startswith("lment")  # A literal match can still be a clipped fragment.
    assert result.data["terms"] == candidate
    assert result.evidence[0].quote == selected[0]
    assert any(issue.code == "source_text_review_required" for issue in result.warnings)
