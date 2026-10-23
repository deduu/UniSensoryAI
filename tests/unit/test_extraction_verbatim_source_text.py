"""Opt-in source-text values are assembled from the exact spans being cited."""

import asyncio
import json
from typing import Any
from unittest.mock import AsyncMock

import pytest
from pydantic import BaseModel, Field, field_validator

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
from src.extraction.settings import ExtractionSettings
from src.paper.schemas.rent_agreement import RentAgreementSchema


def _setup(
    sources: list[str],
    properties: dict[str, Any],
    values: dict[str, Any],
    *,
    strategy: str = "verbatim",
    selections: list[dict[str, Any]] | None = None,
    max_input_chars: int = 180000,
    definitions: dict[str, Any] | None = None,
) -> tuple[ExtractionService, AsyncMock, DocumentResult, ExternalSchema]:
    document = DocumentResult(
        document_id="source",
        source_name="contract.pdf",
        content_mode="text",
        text="\n".join(sources),
        pages=tuple(
            PageContent(
                page_number=index + 1,
                width=600,
                height=800,
                text_blocks=(
                    TextBlock(block_id=f"p{index + 1}", page_number=index + 1, text=text),
                ),
            )
            for index, text in enumerate(sources)
        ),
    )
    schema = ExternalSchema(
        schema_id="host.contract",
        json_schema={
            "type": "object",
            "properties": properties,
            "additionalProperties": False,
            "$defs": definitions or {},
        },
    )
    gateway = AsyncMock()
    gateway.describe = lambda profile: ModelDescriptor(
        model_id="host", max_input_chars=max_input_chars
    )

    async def respond(profile: str, request: ModelRequest) -> ModelResponse:
        if request.prompt.startswith("Source-text span selection:"):
            spans = json.loads(request.prompt.split("\nSource spans:\n", 1)[1])
            result = selections or [
                {"field_path": "/terms", "clauses": [[x["span_id"] for x in spans]]}
            ]
            payload = {"selections": result}
        else:
            payload = {
                "data": values,
                "evidence": [{"field_path": "/terms", "source_ids": ["p1"], "quote": sources[0]}],
            }
        return ModelResponse(content=json.dumps(payload), model_id="host")

    gateway.generate.side_effect = respond
    settings = ExtractionSettings(
        source_text_strategy=strategy,
        source_text_schema_ids=("host.contract",),
        field_review_batch_size=0,
        evidence_repair_attempts=0,
    )
    return (
        ExtractionService(reader=AsyncMock(), gateway=gateway, settings=settings),
        gateway,
        document,
        schema,
    )


@pytest.mark.asyncio
async def test_verbatim_cancellation_preserves_actor_sent_trigger_and_cross_page_conditions() -> (
    None
):
    sources = [
        "Tenant may cancel only before commencement if the permit is refused for any reason;",
        "in that case Landlord must refund payments within seven days after notice is SENT, not received.",
    ]
    service, gateway, document, schema = _setup(
        sources,
        {"terms": {"type": "string", "x-source-text": True}},
        {"terms": "All cancellation refunds are due after notice is received."},
    )
    result = await service.extract_fields(document, schema)
    assert result.data["terms"] == "\n\n".join(sources)
    assert [(item.source_ids, item.quote) for item in result.evidence] == [
        (("p1",), sources[0]),
        (("p2",), sources[1]),
    ]
    assert gateway.generate.await_count == 2
    assert any(item.code == "source_text_review_required" for item in result.warnings)
    assert not any(item.code == "source_text_grounded" for item in result.warnings)


@pytest.mark.asyncio
async def test_verbatim_values_do_not_rewrite_other_party_or_drop_alternative_conditions() -> None:
    source = "If performance of the affected party is delayed OR impossible, the OTHER party may terminate."
    service, _, document, schema = _setup(
        [source],
        {"terms": {"type": "string", "x-source-text": True}},
        {"terms": "Tenant may terminate only if performance is impossible."},
    )
    result = await service.extract_fields(document, schema)
    assert result.data["terms"] == source
    assert result.evidence[0].quote == result.data["terms"]


@pytest.mark.asyncio
async def test_source_text_arrays_group_clauses_and_keep_scalar_workflows_unchanged() -> None:
    sources = [
        "Deposit after complete documents AND",
        "signed confirmation OR the stated date.",
        "Other party may terminate.",
    ]
    service, _, document, schema = _setup(
        sources,
        {
            "terms": {"type": "array", "items": {"type": "string"}, "x-source-text": True},
            "currency": {"type": "string"},
        },
        {"terms": ["Wrong deposit condition."], "currency": "EUR"},
        selections=[
            {
                "field_path": "/terms",
                "clauses": [["source-span-1", "source-span-0"], ["source-span-2"]],
            }
        ],
    )
    result = await service.extract_fields(document, schema)
    assert result.data == {"terms": ["\n\n".join(sources[:2]), sources[2]], "currency": "EUR"}
    assert [item.field_path for item in result.evidence] == ["/terms/0", "/terms/0", "/terms/1"]


@pytest.mark.asyncio
async def test_unknown_span_ids_keep_candidate_and_explicit_unresolved_review() -> None:
    service, _, document, schema = _setup(
        ["Complete conditions."],
        {"terms": {"type": "string", "x-source-text": True}},
        {"terms": "Retained candidate."},
        selections=[{"field_path": "/terms", "clauses": [["invented"]]}],
    )
    result = await service.extract_fields(document, schema)
    assert result.data["terms"] == "Retained candidate."
    assert any(item.code == "source_text_selection_incomplete" for item in result.warnings)


@pytest.mark.asyncio
async def test_schema_length_limit_never_truncates_a_conditional_clause() -> None:
    service, _, document, schema = _setup(
        ["A complete clause with conditions AND an exception."],
        {"terms": {"type": "string", "maxLength": 10, "x-source-text": True}},
        {"terms": "Retained"},
    )
    result = await service.extract_fields(document, schema)
    assert result.data["terms"] == "Retained"
    assert any(item.code == "source_text_selection_incomplete" for item in result.warnings)


@pytest.mark.asyncio
async def test_default_candidate_strategy_preserves_existing_annotated_workflows() -> None:
    service, gateway, document, schema = _setup(
        ["Original source."],
        {"terms": {"type": "string", "x-source-text": True}},
        {"terms": "Existing candidate."},
        strategy="candidate",
    )
    result = await service.extract_fields(document, schema)
    assert result.data["terms"] == "Existing candidate."
    assert gateway.generate.await_count == 1


@pytest.mark.asyncio
async def test_unannotated_fields_are_never_rewritten_by_the_source_text_pass() -> None:
    service, gateway, document, schema = _setup(
        ["Original source."],
        {"terms": {"type": "string"}},
        {"terms": "Existing summary."},
    )
    result = await service.extract_fields(document, schema)
    assert result.data["terms"] == "Existing summary."
    assert gateway.generate.await_count == 1


def test_paper_clause_fields_allow_complete_long_clauses_without_relaxing_other_text() -> None:
    text = "Complete source clause. " * 250
    agreement = RentAgreementSchema(
        payment_schedule=text, renewal_terms=text, other_key_terms=(text,)
    )
    assert agreement.payment_schedule == text.strip()
    with pytest.raises(ValueError):
        RentAgreementSchema(location=text)


@pytest.mark.asyncio
async def test_source_text_selection_resolves_nested_refs_and_preserves_other_nested_fields() -> (
    None
):
    service, gateway, document, schema = _setup(
        ["Owner refunds after notice is sent."],
        {
            "nested": {
                "type": "object",
                "properties": {"term": {"$ref": "#/$defs/narrative"}, "code": {"type": "string"}},
            }
        },
        {"nested": {"term": "Incorrect", "code": "KEEP"}},
        selections=[{"field_path": "/nested/term", "clauses": [["source-span-0"]]}],
        definitions={"narrative": {"type": ["string", "null"], "x-source-text": True}},
    )
    result = await service.extract_fields(document, schema)
    assert result.data == {
        "nested": {"term": "Owner refunds after notice is sent.", "code": "KEEP"}
    }
    assert any(item.field_path == "/nested/term" for item in result.evidence)
    assert gateway.generate.await_count == 2


@pytest.mark.asyncio
async def test_context_budget_never_selects_from_a_silently_truncated_source() -> None:
    service, gateway, document, schema = _setup(
        ["Complete source clause."],
        {"terms": {"type": "string", "x-source-text": True}},
        {"terms": "Retained"},
    )
    descriptions = 0

    def shrinking_context(profile: str) -> ModelDescriptor:
        nonlocal descriptions
        descriptions += 1
        return ModelDescriptor(
            model_id="host", max_input_chars=180000 if descriptions == 1 else 1024
        )

    gateway.describe = shrinking_context
    result = await service.extract_fields(document, schema)
    assert result.data["terms"] == "Retained"
    assert any(item.code == "source_text_selection_incomplete" for item in result.warnings)
    assert gateway.generate.await_count == 1


@pytest.mark.asyncio
async def test_adjacent_source_paragraphs_are_selectable_without_clipping_inside_paragraphs() -> (
    None
):
    source = "First ground AND all its conditions.\n\nRefund for that ground after notice is sent."
    service, _, document, schema = _setup(
        [source],
        {"terms": {"type": "string", "x-source-text": True}},
        {"terms": "Incorrect"},
    )
    result = await service.extract_fields(document, schema)
    assert result.data["terms"] == source
    assert [item.quote for item in result.evidence] == source.split("\n\n")


@pytest.mark.asyncio
async def test_provider_failure_is_explicit_and_keeps_original_values_and_evidence() -> None:
    service, gateway, document, schema = _setup(
        ["Complete clause."],
        {"terms": {"type": "string", "x-source-text": True}},
        {"terms": "Retained"},
    )
    original = gateway.generate.side_effect

    async def fail_selection(profile: str, request: ModelRequest) -> ModelResponse:
        if request.prompt.startswith("Source-text span selection:"):
            raise RuntimeError("private provider failure")
        return await original(profile, request)

    gateway.generate.side_effect = fail_selection
    result = await service.extract_fields(document, schema)
    assert result.data["terms"] == "Retained"
    assert result.evidence[0].quote == "Complete clause."
    assert gateway.generate.await_count == 3
    assert any(item.code == "source_text_selection_incomplete" for item in result.warnings)
    assert "private provider failure" not in str(result.warnings)


@pytest.mark.asyncio
async def test_scanned_page_without_ocr_prevents_complete_source_selection() -> None:
    service, gateway, document, schema = _setup(
        ["Clause starts here."],
        {"terms": {"type": "string", "x-source-text": True}},
        {"terms": "Retained"},
    )
    document = document.model_copy(
        update={
            "pages": document.pages
            + (PageContent(page_number=2, width=600, height=800, is_scanned=True),)
        }
    )
    result = await service.extract_fields(document, schema)
    assert result.data["terms"] == "Retained"
    assert any(item.code == "source_text_selection_incomplete" for item in result.warnings)
    assert gateway.generate.await_count == 1


@pytest.mark.asyncio
async def test_source_selection_cancellation_propagates_without_retry() -> None:
    service, gateway, document, schema = _setup(
        ["Complete clause."],
        {"terms": {"type": "string", "x-source-text": True}},
        {"terms": "Retained"},
    )
    original = gateway.generate.side_effect

    async def cancel_selection(profile: str, request: ModelRequest) -> ModelResponse:
        if request.prompt.startswith("Source-text span selection:"):
            raise asyncio.CancelledError
        return await original(profile, request)

    gateway.generate.side_effect = cancel_selection
    with pytest.raises(asyncio.CancelledError):
        await service.extract_fields(document, schema)
    assert gateway.generate.await_count == 2


@pytest.mark.asyncio
async def test_schema_not_in_allowlist_keeps_candidates_even_with_annotation() -> None:
    service, gateway, document, schema = _setup(
        ["Complete clause."],
        {"terms": {"type": "string", "x-source-text": True}},
        {"terms": "Retained"},
    )
    schema = schema.model_copy(update={"schema_id": "other.contract"})
    result = await service.extract_fields(document, schema)
    assert result.data["terms"] == "Retained"
    assert gateway.generate.await_count == 1


@pytest.mark.asyncio
async def test_host_validator_rewrite_does_not_claim_the_final_value_is_literal() -> None:
    class NormalizedContract(BaseModel):
        terms: str = Field(json_schema_extra={"x-source-text": True})

        @field_validator("terms")
        @classmethod
        def normalize_terms(cls, value: str) -> str:
            return value.upper()

    source = "Other party may terminate after notice is sent."
    _, gateway, document, _ = _setup(
        [source], {"terms": {"type": "string", "x-source-text": True}}, {"terms": "Incorrect"}
    )
    service = ExtractionService(
        reader=AsyncMock(),
        gateway=gateway,
        settings=ExtractionSettings(
            source_text_strategy="verbatim",
            source_text_schema_ids=("NormalizedContract",),
            evidence_repair_attempts=0,
        ),
    )
    result = await service.extract_fields(document, NormalizedContract)
    assert result.data["terms"] == source.upper()
    assert result.evidence[0].quote == source
    assert any(
        issue.code == "source_text_host_transformed" and issue.field_path == "/terms"
        for issue in result.warnings
    )
    reviews = [issue for issue in result.warnings if issue.code == "source_text_review_required"]
    assert reviews and not any(
        "copies selected source paragraphs exactly" in issue.message for issue in reviews
    )


@pytest.mark.asyncio
async def test_host_array_normalization_marks_only_the_changed_source_text_leaf() -> None:
    class NormalizedClauses(BaseModel):
        terms: list[str] = Field(json_schema_extra={"x-source-text": True})

        @field_validator("terms")
        @classmethod
        def normalize_one_clause(cls, value: list[str]) -> list[str]:
            return [value[0], value[1].upper()]

    sources = ["Unchanged first clause.", "Changed second clause."]
    _, gateway, document, _ = _setup(
        sources,
        {"terms": {"type": "array", "items": {"type": "string"}, "x-source-text": True}},
        {"terms": ["Incorrect"]},
        selections=[{"field_path": "/terms", "clauses": [["source-span-0"], ["source-span-1"]]}],
    )
    service = ExtractionService(
        reader=AsyncMock(),
        gateway=gateway,
        settings=ExtractionSettings(
            source_text_strategy="verbatim",
            source_text_schema_ids=("NormalizedClauses",),
            evidence_repair_attempts=0,
        ),
    )
    result = await service.extract_fields(document, NormalizedClauses)
    assert result.data["terms"] == [sources[0], sources[1].upper()]
    assert [item.quote for item in result.evidence] == sources
    assert [
        issue.field_path
        for issue in result.warnings
        if issue.code == "source_text_host_transformed"
    ] == ["/terms/1"]
    reviews = {
        issue.field_path: issue.message
        for issue in result.warnings
        if issue.code == "source_text_review_required"
    }
    assert "copies selected source paragraphs exactly" in reviews["/terms/0"]
    assert "copies selected source paragraphs exactly" not in reviews["/terms/1"]
