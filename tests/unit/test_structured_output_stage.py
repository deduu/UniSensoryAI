"""Tests for src/pipeline/stages/structured_output_stage.py."""

import json
import sys
from typing import Any, Dict, List
from unittest.mock import MagicMock

import pytest

# Stub heavy deps before pipeline imports trigger them.
_MOCK_MODULES = [
    "torch", "torch.cuda", "torch.nn", "torch.nn.functional",
    "torchvision", "torchvision.transforms",
    "transformers", "accelerate", "bitsandbytes",
]
for _mod in _MOCK_MODULES:
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()

from src.inference.concurrency import reset_registry
from src.pipeline.stages.structured_output_stage import (
    StructuredOutputStage,
    _build_prompt,
    _extract_json_payload,
)
from src.structured import InvoiceSchema, SchemaRegistry


@pytest.fixture(autouse=True)
def _reset_singletons(monkeypatch):
    reset_registry()
    # Bypass real config reads; provide a tiny inline limit so the registry
    # never touches the YAML during these tests.
    monkeypatch.setattr(
        "src.inference.concurrency.ConfigLoader.get_model_config",
        lambda model_id, validate=True: {"provider": "openai", "concurrency": 8},
    )
    yield
    reset_registry()


class _ScriptedModel:
    """Returns a queue of pre-baked replies in order."""

    def __init__(self, replies: List[str]) -> None:
        self._replies = list(replies)
        self.calls: List[Dict[str, Any]] = []

    def process(self, image: bytes, prompt: str) -> Dict[str, str]:
        self.calls.append({"prompt": prompt, "image_bytes": len(image)})
        if not self._replies:
            return {"content": ""}
        return {"content": self._replies.pop(0)}


def _valid_invoice_json() -> str:
    return json.dumps(
        {
            "vendor_name": "Acme",
            "invoice_number": "INV-42",
            "total": 99.50,
            "line_items": [
                {"description": "Widget", "quantity": 2, "unit_price": 49.75, "line_total": 99.50}
            ],
        }
    )


class TestJsonExtraction:
    def test_plain_object(self):
        assert _extract_json_payload('{"a": 1}') == '{"a": 1}'

    def test_object_after_prose(self):
        text = "Sure, here it is:\n{\"a\": 1, \"b\": [2, 3]}\nlet me know."
        out = _extract_json_payload(text)
        assert out is not None
        assert json.loads(out) == {"a": 1, "b": [2, 3]}

    def test_code_fence(self):
        text = "```json\n{\"a\": 1}\n```"
        out = _extract_json_payload(text)
        assert out is not None
        assert json.loads(out) == {"a": 1}

    def test_nested_braces(self):
        text = 'noise {"a": {"b": 1}} trailing'
        assert json.loads(_extract_json_payload(text)) == {"a": {"b": 1}}

    def test_string_with_brace(self):
        text = '{"label": "hello {world}"}'
        assert json.loads(_extract_json_payload(text)) == {"label": "hello {world}"}

    def test_no_object(self):
        assert _extract_json_payload("no json here") is None
        assert _extract_json_payload("") is None


class TestPromptBuilder:
    def test_includes_schema(self):
        prompt = _build_prompt(InvoiceSchema, "Some text")
        assert "vendor_name" in prompt
        assert "Some text" in prompt
        assert "previous output failed" not in prompt.lower()

    def test_retry_embeds_prior_error(self):
        prompt = _build_prompt(InvoiceSchema, "Some text", prior_error="field missing")
        assert "field missing" in prompt
        assert "Fix" in prompt


class TestStructuredOutputStage:
    @pytest.mark.asyncio
    async def test_skips_when_no_subtype(self):
        model = _ScriptedModel([_valid_invoice_json()])
        stage = StructuredOutputStage()
        ctx = {
            "raw_results": ["some text"],
            "model_id": "m",
            "model_instance": model,
            "document_subtype": None,
        }
        result = await stage.execute(ctx)
        assert "structured_chunks" not in result or not result.get("structured_chunks")
        assert model.calls == []

    @pytest.mark.asyncio
    async def test_happy_path_invoice(self):
        model = _ScriptedModel([_valid_invoice_json()])
        stage = StructuredOutputStage()
        ctx = {
            "raw_results": ["Vendor: Acme\nInvoice: INV-42\nTotal: 99.50"],
            "model_id": "m",
            "model_instance": model,
            "document_subtype": "invoice",
        }
        result = await stage.execute(ctx)

        assert len(model.calls) == 1
        chunks = result["structured_chunks"]
        assert len(chunks) == 1
        assert chunks[0]["schema_id"] == "invoice"
        content = chunks[0]["content"]
        assert content["vendor_name"] == "Acme"
        assert content["total"] == 99.50
        assert len(content["line_items"]) == 1

    @pytest.mark.asyncio
    async def test_retries_on_invalid_then_succeeds(self):
        model = _ScriptedModel([
            json.dumps({"vendor_name": "Acme", "invoice_number": "INV-1"}),  # missing total
            _valid_invoice_json(),
        ])
        stage = StructuredOutputStage()
        ctx = {
            "raw_results": ["text"],
            "model_id": "m",
            "model_instance": model,
            "document_subtype": "invoice",
        }
        result = await stage.execute(ctx)

        assert len(model.calls) == 2
        # Second call must include the prior error in the prompt.
        assert "previous output failed" in model.calls[1]["prompt"].lower()
        assert len(result["structured_chunks"]) == 1
        assert result.get("validation_errors", []) == []

    @pytest.mark.asyncio
    async def test_records_validation_error_after_retry_fails(self):
        bad = json.dumps({"vendor_name": "Acme"})  # missing required fields
        model = _ScriptedModel([bad, bad])
        stage = StructuredOutputStage()
        ctx = {
            "raw_results": ["text"],
            "model_id": "m",
            "model_instance": model,
            "document_subtype": "invoice",
        }
        result = await stage.execute(ctx)

        assert len(model.calls) == 2
        assert "structured_chunks" not in result or not result.get("structured_chunks")
        errors = result["validation_errors"]
        assert len(errors) == 1
        assert errors[0]["stage"] == "structured_output"
        assert errors[0]["schema_id"] == "invoice"

    @pytest.mark.asyncio
    async def test_skips_when_registry_returns_none(self):
        model = _ScriptedModel([_valid_invoice_json()])
        stage = StructuredOutputStage(registry=SchemaRegistry(default=None))
        ctx = {
            "raw_results": ["text"],
            "model_id": "m",
            "model_instance": model,
            "document_subtype": "unknown-subtype",
        }
        result = await stage.execute(ctx)
        assert model.calls == []
        assert not result.get("structured_chunks")

    @pytest.mark.asyncio
    async def test_text_length_capped(self):
        long_text = "x" * 50_000
        model = _ScriptedModel([_valid_invoice_json()])
        stage = StructuredOutputStage(max_text_chars=1000)
        ctx = {
            "raw_results": [long_text],
            "model_id": "m",
            "model_instance": model,
            "document_subtype": "invoice",
        }
        await stage.execute(ctx)
        # Prompt body must not embed the full 50k chars.
        sent_prompt = model.calls[0]["prompt"]
        # The schema JSON adds overhead, but body should be ~1000 chars.
        assert sent_prompt.count("x") <= 1000 + 10

    def test_validate_input(self):
        stage = StructuredOutputStage()
        assert stage.validate_input({}) is False
        assert stage.validate_input({"raw_results": ["x"], "model_id": "m"}) is False
        assert (
            stage.validate_input(
                {"raw_results": ["x"], "model_id": "m", "model_instance": object()}
            )
            is True
        )
