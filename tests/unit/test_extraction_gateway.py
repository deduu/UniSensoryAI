"""Model profile routing, validation, and resource controls."""

import asyncio
import time

import pytest
from pydantic import ValidationError

from src.extraction.contracts import ImageAsset, ModelDescriptor, ModelRequest, ModelResponse
from src.extraction.errors import ExtractionError
from src.extraction.model_gateway import ModelGateway
from src.extraction.ports.generation import BaseGenerationProvider


class RecordingProvider(BaseGenerationProvider):
    def __init__(self, *, delay: float = 0, concurrency: int = 1) -> None:
        self._descriptor = ModelDescriptor(model_id="fake", concurrency=concurrency)
        self.delay = delay
        self.calls = 0
        self.active = 0
        self.maximum = 0
        self.timestamps: list[float] = []

    @property
    def descriptor(self) -> ModelDescriptor:
        return self._descriptor

    async def complete(self, request: ModelRequest) -> ModelResponse:
        self.calls += 1
        self.timestamps.append(time.monotonic())
        self.active += 1
        self.maximum = max(self.maximum, self.active)
        try:
            await asyncio.sleep(self.delay)
            return ModelResponse(content="ok", model_id="fake")
        finally:
            self.active -= 1


@pytest.mark.asyncio
async def test_gateway_routing_and_shared_provider_concurrency() -> None:
    provider = RecordingProvider(delay=0.01, concurrency=2)
    gateway = ModelGateway({"ocr": provider, "fields": provider})
    assert gateway.describe("ocr") == provider.descriptor
    await asyncio.gather(
        *(
            gateway.generate("ocr" if i % 2 else "fields", ModelRequest(prompt="text"))
            for i in range(6)
        )
    )
    assert provider.maximum == 2
    assert provider.calls == 6


@pytest.mark.parametrize(
    "profile,model_request,code",
    [
        ("unknown", ModelRequest(prompt="text"), "unknown_model_profile"),
        ("text", ModelRequest(prompt="x" * 48001), "context_limit"),
        (
            "text",
            ModelRequest(
                prompt="text", images=(ImageAsset(asset_id="i", page_number=1, data_base64="cG5n"),)
            ),
            "unsupported_model_features",
        ),
    ],
)
@pytest.mark.asyncio
async def test_gateway_checks_compatibility_before_call(
    profile: str, model_request: ModelRequest, code: str
) -> None:
    provider = RecordingProvider()
    gateway = ModelGateway({"text": provider})
    with pytest.raises(ExtractionError) as caught:
        await gateway.generate(profile, model_request)
    assert caught.value.code == code
    assert provider.calls == 0


@pytest.mark.asyncio
async def test_gateway_rate_limit_counts_all_profiles() -> None:
    provider = RecordingProvider(concurrency=20)
    gateway = ModelGateway({"a": provider, "b": provider})
    await asyncio.gather(
        *(gateway.generate("a" if i % 2 else "b", ModelRequest(prompt="text")) for i in range(11))
    )
    assert provider.timestamps[10] - provider.timestamps[0] >= 0.98


@pytest.mark.asyncio
async def test_gateway_timeout_and_cancellation() -> None:
    provider = RecordingProvider(delay=1)
    gateway = ModelGateway({"a": provider}, timeout_seconds=0.01)
    with pytest.raises(ExtractionError) as caught:
        await gateway.generate("a", ModelRequest(prompt="text"))
    assert caught.value.code == "model_timeout"
    assert provider.active == 0
    task = asyncio.create_task(
        ModelGateway({"a": provider}).generate("a", ModelRequest(prompt="text"))
    )
    await asyncio.sleep(0.01)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.asyncio
async def test_gateway_sanitizes_unexpected_and_typed_provider_failures() -> None:
    provider = RecordingProvider()

    async def fail(request: ModelRequest) -> ModelResponse:
        raise RuntimeError("SECRET API KEY document text")

    provider.complete = fail
    gateway = ModelGateway({"a": provider})
    with pytest.raises(ExtractionError) as caught:
        await gateway.generate("a", ModelRequest(prompt="text"))
    assert caught.value.code == "provider_error"
    assert "SECRET" not in str(caught.value)

    async def typed_fail(model_request: ModelRequest) -> ModelResponse:
        raise ExtractionError("model_response_invalid", "SECRET document")

    provider.complete = typed_fail
    with pytest.raises(ExtractionError) as caught:
        await gateway.generate("a", ModelRequest(prompt="text"))
    assert caught.value.code == "model_response_invalid"
    assert "SECRET" not in str(caught.value)


@pytest.mark.asyncio
async def test_gateway_rejects_untyped_and_truncated_provider_results() -> None:
    provider = RecordingProvider()
    gateway = ModelGateway({"a": provider})

    async def invalid(model_request: ModelRequest) -> dict[str, str]:
        return {"content": "untyped"}

    provider.complete = invalid
    with pytest.raises(ExtractionError) as caught:
        await gateway.generate("a", ModelRequest(prompt="text"))
    assert caught.value.code == "model_response_invalid"

    async def truncated(model_request: ModelRequest) -> ModelResponse:
        return ModelResponse(content="partial", model_id="fake", finish_reason="length")

    provider.complete = truncated
    with pytest.raises(ExtractionError) as caught:
        await gateway.generate("a", ModelRequest(prompt="text"))
    assert caught.value.code == "model_response_invalid"


def test_gateway_validates_operational_configuration() -> None:
    with pytest.raises(ValidationError):
        ModelGateway({"a": RecordingProvider()}, calls_per_second=11)
    with pytest.raises(ValidationError):
        ModelGateway({"a": RecordingProvider()}, timeout_seconds=61)
