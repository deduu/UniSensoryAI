"""Meter every attempted model call without mixing concurrent extraction jobs."""

import asyncio
import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import httpx
import pytest
from pydantic import ValidationError

from src.extraction.composition import build_extraction_service
from src.extraction.contracts import ModelDescriptor, ModelRequest, ModelResponse
from src.extraction.contracts.usage import ModelPricing
from src.extraction.errors import ExtractionError
from src.extraction.model_gateway import ModelGateway
from src.extraction.ports import BaseGenerationProvider
from src.extraction.providers import OpenAICompatibleGenerationProvider
from src.extraction.providers._validation import normalize_response
from src.extraction.usage import capture_model_usage


def pricing(**changes: object) -> ModelPricing:
    return ModelPricing.model_validate(
        {
            "pricing_id": "host-public-estimate-2026-10-17",
            "model_id": "host-model",
            "currency": "USD",
            "input_per_million": "2.50",
            "output_per_million": "10.00",
            "cached_input_per_million": "1.25",
            "source": "https://pricing.example/models/host-model",
            "as_of": "2026-10-17",
            **changes,
        }
    )


class UsageProvider(BaseGenerationProvider):
    @property
    def descriptor(self) -> ModelDescriptor:
        return ModelDescriptor(model_id="host-model", concurrency=4)

    async def complete(self, request: ModelRequest) -> ModelResponse:
        await asyncio.sleep(0)
        amount = int(request.prompt)
        return ModelResponse(
            content="ok",
            model_id="host-model",
            usage={"prompt_tokens": amount, "completion_tokens": 5, "cached_input_tokens": 2},
        )


@pytest.mark.asyncio
async def test_meter_retains_every_profile_call_and_decimal_pricing_snapshot() -> None:
    gateway = ModelGateway(
        {"vision": UsageProvider(), "fields": UsageProvider()},
        pricing={"vision": pricing(), "fields": pricing()},
        provider_names={"vision": "host-adapter", "fields": "host-adapter"},
    )
    with capture_model_usage() as meter:
        await gateway.generate("vision", ModelRequest(prompt="10", purpose="ocr"))
        await gateway.generate("fields", ModelRequest(prompt="20", purpose="fields"))
        await gateway.generate("fields", ModelRequest(prompt="30", purpose="fields"))
    usage = meter.snapshot()
    assert (usage.call_count, usage.measured_call_count) == (3, 3)
    assert (usage.input_tokens, usage.output_tokens, usage.total_tokens) == (60, 15, 75)
    assert usage.coverage == usage.cost_coverage == "complete"
    assert usage.estimated_cost == Decimal("0.0002925")
    assert usage.currency == "USD"
    assert [call.purpose for call in usage.calls] == ["ocr", "fields", "fields"]
    assert [call.sequence for call in usage.calls] == [1, 2, 3]
    assert usage.calls[0].provider == "host-adapter"
    assert usage.calls[0].pricing.as_of == date(2026, 10, 17)
    payload = json.loads(usage.model_dump_json())
    assert payload["estimated_cost"] == "0.0002925"
    assert payload["calls"][0]["pricing"]["input_per_million"] == "2.50"


@pytest.mark.asyncio
async def test_shared_gateway_scopes_do_not_mix_jobs_and_nested_capture_restores_parent() -> None:
    gateway = ModelGateway({"fields": UsageProvider()})

    async def job(amount: int) -> object:
        with capture_model_usage() as meter:
            await asyncio.gather(
                gateway.generate("fields", ModelRequest(prompt=str(amount))),
                gateway.generate("fields", ModelRequest(prompt=str(amount))),
            )
        return meter.snapshot()

    first, second = await asyncio.gather(job(10), job(100))
    assert first.input_tokens == 20
    assert second.input_tokens == 200
    with capture_model_usage() as outer:
        with capture_model_usage() as inner:
            await gateway.generate("fields", ModelRequest(prompt="10"))
        await gateway.generate("fields", ModelRequest(prompt="20"))
    assert inner.snapshot().input_tokens == 10
    assert outer.snapshot().input_tokens == 20
    await gateway.generate("fields", ModelRequest(prompt="100"))
    assert outer.snapshot().input_tokens == 20


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["length", "refusal", "malformed"])
async def test_billable_invalid_provider_output_keeps_nested_usage(failure: str) -> None:
    def reply(request: httpx.Request) -> httpx.Response:
        message = {"content": "partial"}
        if failure == "refusal":
            message["refusal"] = "private document refusal detail"
        body = {
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "prompt_tokens_details": {"cached_tokens": 4},
            },
            "choices": [
                {"message": message, "finish_reason": "length" if failure == "length" else "stop"}
            ],
        }
        if failure == "malformed":
            body["choices"] = []
        return httpx.Response(200, json=body)

    async with httpx.AsyncClient(transport=httpx.MockTransport(reply)) as client:
        provider = OpenAICompatibleGenerationProvider(
            ModelDescriptor(model_id="host-model"),
            base_url="https://host.example/v1",
            client=client,
        )
        gateway = ModelGateway({"fields": provider}, pricing={"fields": pricing()})
        with capture_model_usage() as meter, pytest.raises(ExtractionError) as caught:
            await gateway.generate("fields", ModelRequest(prompt="private document"))
    usage = meter.snapshot()
    assert caught.value.code == "model_response_invalid"
    assert usage.call_count == 1
    assert usage.calls[0].status == "failed"
    assert usage.calls[0].cached_input_tokens == 4
    assert usage.total_tokens == 15
    assert usage.coverage == usage.cost_coverage == "complete"
    assert usage.estimated_cost == Decimal("0.000070")
    assert "private" not in usage.model_dump_json()


@pytest.mark.asyncio
async def test_unreported_failed_attempt_leaves_known_subtotal_explicitly_partial() -> None:
    provider = UsageProvider()
    gateway = ModelGateway({"fields": provider}, pricing={"fields": pricing()})
    with capture_model_usage() as meter:
        await gateway.generate("fields", ModelRequest(prompt="10"))

        async def fail(request: ModelRequest) -> ModelResponse:
            raise RuntimeError("private credentials")

        provider.complete = fail
        with pytest.raises(ExtractionError):
            await gateway.generate("fields", ModelRequest(prompt="20"))
    usage = meter.snapshot()
    assert usage.call_count == 2 and usage.measured_call_count == 1
    assert usage.total_tokens == 15
    assert usage.coverage == usage.cost_coverage == "partial"
    assert usage.calls[1].total_tokens is None
    assert usage.calls[1].error_code == "provider_error"
    assert "private" not in usage.model_dump_json()


@pytest.mark.asyncio
async def test_timeout_is_an_unknown_attempt_but_preflight_failure_is_not_a_call() -> None:
    provider = UsageProvider()

    async def slow(request: ModelRequest) -> ModelResponse:
        await asyncio.sleep(1)
        return ModelResponse(content="late", model_id="host-model")

    provider.complete = slow
    gateway = ModelGateway({"fields": provider}, timeout_seconds=0.01)
    with capture_model_usage() as meter:
        with pytest.raises(ExtractionError):
            await gateway.generate("fields", ModelRequest(prompt="x" * 48001))
        with pytest.raises(ExtractionError):
            await gateway.generate("fields", ModelRequest(prompt="10"))
    usage = meter.snapshot()
    assert usage.call_count == 1
    assert usage.coverage == usage.cost_coverage == "unavailable"
    assert usage.total_tokens is None and usage.estimated_cost is None
    assert usage.calls[0].status == "cancelled"


def test_nested_usage_normalization_preserves_exact_raw_content_and_safe_counters() -> None:
    response = normalize_response(
        "**exact raw**\n",
        "host-model",
        "stop",
        {
            "input_tokens": 10,
            "output_tokens": 3,
            "input_tokens_details": {"cached_tokens": 2},
            "secret": "private",
        },
    )
    assert response.content == "**exact raw**\n"
    assert response.usage["cached_input_tokens"] == 2
    assert "secret" not in response.usage


def test_pricing_validates_identity_decimals_and_rejects_nonfinite_or_negative_rates() -> None:
    for value in ["-1", "NaN", "Infinity"]:
        with pytest.raises(ValidationError):
            pricing(input_per_million=value)
    with pytest.raises(ValueError):
        ModelGateway({"fields": UsageProvider()}, pricing={"fields": pricing(model_id="other")})


@pytest.mark.asyncio
async def test_missing_rates_or_cached_counter_never_invent_cost() -> None:
    provider = UsageProvider()
    with capture_model_usage() as meter:
        await ModelGateway({"fields": provider}).generate("fields", ModelRequest(prompt="10"))
    assert meter.snapshot().coverage == "complete"
    assert meter.snapshot().estimated_cost is None
    assert meter.snapshot().cost_coverage == "unavailable"

    async def no_cache(request: ModelRequest) -> ModelResponse:
        return ModelResponse(
            content="ok", model_id="host-model", usage={"input_tokens": 10, "output_tokens": 5}
        )

    provider.complete = no_cache
    with capture_model_usage() as meter:
        await ModelGateway({"fields": provider}, pricing={"fields": pricing()}).generate(
            "fields", ModelRequest(prompt="10")
        )
    assert meter.snapshot().estimated_cost is None
    assert meter.snapshot().cost_coverage == "unavailable"


@pytest.mark.asyncio
async def test_runtime_yaml_injects_bound_pricing_without_any_default_rate(tmp_path: Path) -> None:
    config = tmp_path / "extraction.yaml"
    config.write_text(
        "profiles:\n  fields:\n    provider: host\n    model_id: host-model\n"
        "    pricing:\n      pricing_id: test-price\n      model_id: host-model\n"
        "      currency: USD\n      input_per_million: '2.50'\n"
        "      output_per_million: '10.00'\n      source: host-configured\n",
        encoding="utf-8",
    )
    service = await build_extraction_service(
        config_path=config, provider_factories={"host": lambda profile: UsageProvider()}
    )
    with capture_model_usage() as meter:
        await service._fields._gateway.generate("fields", ModelRequest(prompt="10"))
    assert meter.snapshot().estimated_cost == Decimal("0.000075")
    assert meter.snapshot().calls[0].provider == "host"
    await service.aclose()


@pytest.mark.asyncio
async def test_resolved_model_mismatch_keeps_usage_but_never_uses_wrong_price() -> None:
    provider = UsageProvider()

    async def other_model(request: ModelRequest) -> ModelResponse:
        return ModelResponse(
            content="ok",
            model_id="other-model",
            usage={"input_tokens": 10, "output_tokens": 5, "cached_input_tokens": 0},
        )

    provider.complete = other_model
    with capture_model_usage() as meter:
        await ModelGateway({"fields": provider}, pricing={"fields": pricing()}).generate(
            "fields", ModelRequest(prompt="10")
        )
    assert meter.snapshot().total_tokens == 15
    assert meter.snapshot().estimated_cost is None
    assert meter.snapshot().calls[0].model_id == "other-model"


@pytest.mark.asyncio
async def test_mixed_currency_prices_remain_separate_and_inconsistent_totals_are_partial() -> None:
    gateway = ModelGateway(
        {"usd": UsageProvider(), "eur": UsageProvider()},
        pricing={"usd": pricing(), "eur": pricing(currency="EUR")},
    )
    with capture_model_usage() as meter:
        await gateway.generate("usd", ModelRequest(prompt="10"))
        await gateway.generate("eur", ModelRequest(prompt="10"))
    assert meter.snapshot().estimated_cost is None
    assert meter.snapshot().currency is None
    assert meter.snapshot().cost_coverage == "partial"
    assert meter.snapshot().calls[0].currency == "USD"
    assert meter.snapshot().calls[1].currency == "EUR"

    async def inconsistent(request: ModelRequest) -> ModelResponse:
        return ModelResponse(
            content="ok",
            model_id="host-model",
            usage={"input_tokens": 10, "output_tokens": 5, "total_tokens": 3},
        )

    provider = UsageProvider()
    provider.complete = inconsistent
    with capture_model_usage() as meter:
        await ModelGateway({"fields": provider}).generate("fields", ModelRequest(prompt="10"))
    assert meter.snapshot().coverage == "unavailable"
    assert meter.snapshot().calls[0].total_tokens == 3


@pytest.mark.asyncio
async def test_legacy_failed_output_retains_safe_billable_usage() -> None:
    from src.extraction.providers.legacy_vision import LegacyVisionGenerationProvider

    class LocalModel:
        def process(self, image: object, prompt: str, **kwargs: object) -> dict[str, object]:
            return {"error": "private payload", "usage": {"input_tokens": 10, "output_tokens": 5}}

        def unload(self) -> None:
            pass

    provider = LegacyVisionGenerationProvider(
        ModelDescriptor(model_id="host-model"), model=LocalModel(), supports_text=True
    )
    with capture_model_usage() as meter, pytest.raises(ExtractionError):
        await ModelGateway({"fields": provider}).generate("fields", ModelRequest(prompt="10"))
    assert meter.snapshot().total_tokens == 15
    assert meter.snapshot().calls[0].status == "failed"
    assert "private" not in meter.snapshot().model_dump_json()


@pytest.mark.asyncio
@pytest.mark.parametrize("finish_reason", ["stop", "length"])
@pytest.mark.parametrize("allowed", [False, True])
async def test_http_actual_model_identity_requires_explicit_price_alias(
    finish_reason: str, allowed: bool
) -> None:
    def reply(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "model": "host-model-dated",
                "usage": {"input_tokens": 10, "output_tokens": 5, "cached_input_tokens": 0},
                "choices": [{"message": {"content": "output"}, "finish_reason": finish_reason}],
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(reply)) as client:
        provider = OpenAICompatibleGenerationProvider(
            ModelDescriptor(model_id="host-model"),
            base_url="https://host.example/v1",
            client=client,
        )
        gateway = ModelGateway(
            {"fields": provider},
            pricing={
                "fields": pricing(
                    allowed_response_model_ids=["host-model-dated"] if allowed else []
                )
            },
        )
        with capture_model_usage() as meter:
            if finish_reason == "length":
                with pytest.raises(ExtractionError):
                    await gateway.generate("fields", ModelRequest(prompt="10"))
            else:
                response = await gateway.generate("fields", ModelRequest(prompt="10"))
                assert response.model_id == "host-model"
    call = meter.snapshot().calls[0]
    assert call.response_model_id == "host-model-dated"
    assert call.model_id == "host-model"
    assert (call.estimated_cost is not None) == allowed


@pytest.mark.asyncio
async def test_chat_adapter_retains_actual_identity_and_nested_cached_usage() -> None:
    from unittest.mock import AsyncMock

    from src.extraction.providers.chat_adapter import ChatGenerationProvider
    from src.orchestration.llm.base import LLMResponse

    response = LLMResponse(
        content="ok",
        model="different-model",
        finish_reason="stop",
        token_usage={"prompt_tokens": 10, "completion_tokens": 5},
        raw={
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "prompt_tokens_details": {"cached_tokens": 2},
            }
        },
    )
    provider = ChatGenerationProvider(
        AsyncMock(complete=AsyncMock(return_value=response)), ModelDescriptor(model_id="host-model")
    )
    with capture_model_usage() as meter:
        await ModelGateway({"fields": provider}, pricing={"fields": pricing()}).generate(
            "fields", ModelRequest(prompt="10")
        )
    call = meter.snapshot().calls[0]
    assert call.cached_input_tokens == 2
    assert call.response_model_id == "different-model"
    assert call.estimated_cost is None
