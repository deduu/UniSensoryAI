"""Bounded evidence completion never changes caller-schema values or source truth."""

import asyncio
import json
from typing import Any
from unittest.mock import AsyncMock

import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError as SchemaValidationError
from pydantic import ValidationError

from src.extraction.contracts import (
    DocumentResult,
    ExternalSchema,
    ModelDescriptor,
    ModelResponse,
    PageContent,
    TextBlock,
)
from src.extraction.errors import ExtractionError
from src.extraction.service import ExtractionService
from src.extraction.settings import ExtractionSettings


def _service(
    values: dict[str, Any],
    responses: list[str | BaseException],
    *,
    settings: ExtractionSettings | None = None,
    native_json: bool = False,
) -> tuple[ExtractionService, AsyncMock, DocumentResult, ExternalSchema]:
    text = "\n".join(str(value) for value in values.values())
    document = DocumentResult(
        document_id="source-hash",
        source_name="source.pdf",
        content_mode="text",
        text=text,
        pages=(
            PageContent(
                page_number=1,
                width=100,
                height=100,
                text_blocks=(TextBlock(block_id="p1-text", page_number=1, text=text),),
            ),
        ),
    )
    schema = ExternalSchema(
        json_schema={
            "type": "object",
            "properties": {key: {"type": "string"} for key in values},
            "required": list(values),
            "additionalProperties": False,
        }
    )
    gateway = AsyncMock()
    gateway.describe = lambda profile: ModelDescriptor(
        model_id="injected-host", supports_native_json=native_json
    )
    gateway.generate.side_effect = [
        (
            value
            if isinstance(value, BaseException)
            else ModelResponse(content=value, model_id="injected-host")
        )
        for value in responses
    ]
    return (
        ExtractionService(reader=AsyncMock(), gateway=gateway, settings=settings),
        gateway,
        document,
        schema,
    )


def _ref(path: str, quote: str, source: str = "p1-text") -> dict[str, Any]:
    return {"field_path": path, "source_ids": [source], "quote": quote}


@pytest.mark.asyncio
@pytest.mark.parametrize("native_json", [False, True])
async def test_empty_evidence_is_completed_for_long_external_schema_without_reextracting_values(
    native_json: bool,
) -> None:
    values = {f"external_field_{index}": f"Source value {index}" for index in range(15)}
    repair = {"evidence": [_ref(f"/{key}", value) for key, value in values.items()]}
    service, gateway, document, schema = _service(
        values,
        [
            json.dumps({"data": values, "evidence": []}),
            json.dumps(repair),
        ],
        native_json=native_json,
    )
    result = await service.extract_fields(document, schema)
    assert result.data == values
    assert len(result.evidence) == 15
    assert result.status == "succeeded"
    assert gateway.generate.await_count == 2
    request = gateway.generate.await_args.args[1]
    assert "External schema:" not in request.prompt
    assert "immutable" in request.prompt
    assert "untrusted" in request.prompt
    assert "literal" in request.prompt
    assert "/external_field_14" in request.prompt
    assert request.images == ()
    assert request.max_output_tokens == ExtractionSettings().max_output_tokens
    if native_json:
        Draft202012Validator(request.json_schema).validate(repair)
        assert request.json_schema["required"] == ["evidence"]
        with pytest.raises(SchemaValidationError):
            Draft202012Validator(request.json_schema).validate({**repair, "data": values})
    else:
        assert request.json_schema is None


@pytest.mark.asyncio
async def test_only_missing_paths_are_repaired_and_existing_verified_evidence_remains() -> None:
    values = {"first": "PO-1", "second": "PO-2"}
    first = _ref("/first", "PO-1")
    service, gateway, document, schema = _service(
        values,
        [
            json.dumps({"data": values, "evidence": [first]}),
            json.dumps({"evidence": [_ref("/second", "PO-2")]}),
        ],
    )
    result = await service.extract_fields(document, schema)
    prompt = gateway.generate.await_args.args[1].prompt
    assert '"/second"' in prompt
    assert '"/first"' not in prompt
    assert [item.field_path for item in result.evidence] == ["/first", "/second"]
    assert result.status == "succeeded"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "invalid",
    [
        _ref("/code", "PO 1"),
        _ref("/code", "PO-1", "not-supplied"),
        _ref("/other", "PO-1"),
    ],
)
async def test_repair_requires_requested_path_supplied_source_and_literal_quote(
    invalid: dict[str, Any],
) -> None:
    service, gateway, document, schema = _service(
        {"code": "PO-1"},
        [
            '{"data":{"code":"PO-1"},"evidence":[]}',
            json.dumps({"evidence": [invalid]}),
            json.dumps({"evidence": [_ref("/code", "PO-1")]}),
        ],
    )
    result = await service.extract_fields(document, schema)
    assert gateway.generate.await_count == 3
    assert result.status == "succeeded"
    assert result.evidence[0].source_ids == ("p1-text",)
    assert result.evidence[0].quote == "PO-1"


@pytest.mark.asyncio
async def test_budget_exhaustion_or_attempt_to_change_data_remains_explicit_partial() -> None:
    service, gateway, document, schema = _service(
        {"code": "PO-1"},
        [
            '{"data":{"code":"PO-1"},"evidence":[]}',
            '{"data":{"code":"CHANGED"},"evidence":[]}',
            '{"evidence":[]}',
        ],
    )
    result = await service.extract_fields(document, schema)
    assert gateway.generate.await_count == 3
    assert result.data == {"code": "PO-1"}
    assert not result.evidence
    assert result.status == "partial"
    assert [issue.code for issue in result.warnings] == ["missing_evidence"]


@pytest.mark.asyncio
async def test_evidence_repair_can_be_disabled_by_validated_host_settings() -> None:
    settings = ExtractionSettings(evidence_repair_attempts=0)
    service, gateway, document, schema = _service(
        {"code": "PO-1"},
        [
            '{"data":{"code":"PO-1"},"evidence":[]}',
        ],
        settings=settings,
    )
    result = await service.extract_fields(document, schema)
    assert gateway.generate.await_count == 1
    assert result.status == "partial"
    with pytest.raises(ValidationError):
        ExtractionSettings(evidence_repair_attempts=4)


@pytest.mark.asyncio
async def test_evidence_completion_provider_failure_retains_business_data() -> None:
    service, _, document, schema = _service(
        {"code": "PO-1"},
        [
            '{"data":{"code":"PO-1"},"evidence":[]}',
            ExtractionError("model_timeout", "private response"),
        ],
    )
    result = await service.extract_fields(document, schema)
    assert result.data == {"code": "PO-1"}
    assert result.status == "partial"
    assert "private" not in result.model_dump_json()


@pytest.mark.asyncio
async def test_cancellation_during_evidence_completion_is_propagated() -> None:
    service, _, document, schema = _service(
        {"code": "PO-1"},
        [
            '{"data":{"code":"PO-1"},"evidence":[]}',
            asyncio.CancelledError(),
        ],
    )
    with pytest.raises(asyncio.CancelledError):
        await service.extract_fields(document, schema)


@pytest.mark.asyncio
async def test_composite_field_keeps_separate_literal_quotes_from_each_supporting_block() -> None:
    value = "First condition and second condition"
    service, gateway, document, schema = _service(
        {"settlement": value},
        [
            json.dumps({"data": {"settlement": value}, "evidence": []}),
            json.dumps(
                {
                    "evidence": [
                        _ref("/settlement", "First condition", "first"),
                        _ref("/settlement", "second condition", "second"),
                    ]
                }
            ),
        ],
    )
    document = document.model_copy(
        update={
            "pages": (
                PageContent(
                    page_number=1,
                    width=100,
                    height=100,
                    text_blocks=(
                        TextBlock(block_id="first", page_number=1, text="First condition"),
                        TextBlock(block_id="second", page_number=1, text="second condition"),
                    ),
                ),
            )
        }
    )
    result = await service.extract_fields(document, schema)
    assert len(result.evidence) == 2
    assert [item.source_ids for item in result.evidence] == [("first",), ("second",)]
    assert result.status == "succeeded"
    assert "separate evidence items" in gateway.generate.await_args.args[1].prompt
