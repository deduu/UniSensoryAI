"""Provider contract tests with no live model or external network."""

import asyncio
import base64
import json
import threading
from typing import Any
from unittest.mock import AsyncMock

import httpx
import pytest
from pydantic import ValidationError

from src.extraction.contracts import ImageAsset, ModelDescriptor, ModelRequest
from src.extraction.errors import ExtractionError
from src.extraction.providers import (
    ChatGenerationProvider,
    LegacyVisionGenerationProvider,
    OpenAICompatibleGenerationProvider,
)
from src.orchestration.llm.base import LLMResponse


def descriptor(**changes: Any) -> ModelDescriptor:
    return ModelDescriptor(model_id="fake-model", **changes)


def image() -> ImageAsset:
    return ImageAsset(asset_id="p1", page_number=1, data_base64=base64.b64encode(b"png").decode())


@pytest.mark.asyncio
async def test_cloud_text_only_native_schema_and_client_ownership() -> None:
    calls: list[dict[str, Any]] = []

    async def handle(request: httpx.Request) -> httpx.Response:
        calls.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": '{"data":{}}'}, "finish_reason": "stop"}],
                "usage": {"total_tokens": 9, "nested": {"cached": 2}},
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handle))
    provider = OpenAICompatibleGenerationProvider(
        descriptor(supports_native_json=True),
        base_url="https://models.example/v1",
        api_key="secret",
        client=client,
    )
    result = await provider.complete(ModelRequest(prompt="Extract", json_schema={"type": "object"}))
    assert calls[0]["messages"][0]["content"] == "Extract"
    assert calls[0]["response_format"]["type"] == "json_schema"
    assert result.usage == {"total_tokens": 9}
    assert "secret" not in result.model_dump_json()
    await provider.aclose()
    assert not client.is_closed
    await client.aclose()


@pytest.mark.asyncio
async def test_cloud_images_and_schema_prompt_fallback() -> None:
    calls: list[dict[str, Any]] = []

    async def handle(request: httpx.Request) -> httpx.Response:
        calls.append(json.loads(request.content))
        return httpx.Response(
            200, json={"choices": [{"message": {"content": "Observed"}, "finish_reason": "stop"}]}
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        provider = OpenAICompatibleGenerationProvider(
            descriptor(supports_images=True), base_url="https://models.example/v1/", client=client
        )
        await provider.complete(
            ModelRequest(
                prompt="Schema is in prompt", images=(image(),), json_schema={"type": "object"}
            )
        )
    blocks = calls[0]["messages"][0]["content"]
    assert blocks[0] == {"type": "text", "text": "Schema is in prompt"}
    assert blocks[1]["image_url"]["url"] == "data:image/png;base64,cG5n"
    assert "response_format" not in calls[0]


@pytest.mark.parametrize(
    "body,code",
    [
        ({"error": {"message": "secret document"}}, "model_response_invalid"),
        ({"choices": []}, "model_response_invalid"),
        ({"choices": [{"message": {"content": None}}]}, "model_response_invalid"),
        (
            {"choices": [{"message": {"content": "partial"}, "finish_reason": "length"}]},
            "model_response_invalid",
        ),
    ],
)
@pytest.mark.asyncio
async def test_cloud_malformed_or_truncated_output_is_failure(
    body: dict[str, Any], code: str
) -> None:
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=body))
    ) as client:
        provider = OpenAICompatibleGenerationProvider(
            descriptor(), base_url="https://models.example/v1", client=client
        )
        with pytest.raises(ExtractionError) as caught:
            await provider.complete(ModelRequest(prompt="private text"))
    assert caught.value.code == code
    assert "private text" not in str(caught.value)
    assert "secret" not in str(caught.value)


@pytest.mark.asyncio
async def test_cloud_http_failure_and_cancel_are_safe() -> None:
    async def failed(_: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("API secret payload")

    async with httpx.AsyncClient(transport=httpx.MockTransport(failed)) as client:
        provider = OpenAICompatibleGenerationProvider(
            descriptor(), base_url="https://models.example/v1", client=client
        )
        with pytest.raises(ExtractionError) as caught:
            await provider.complete(ModelRequest(prompt="text"))
        assert caught.value.code == "provider_error"
        assert "secret" not in str(caught.value)

    async def cancelled(_: httpx.Request) -> httpx.Response:
        raise asyncio.CancelledError

    async with httpx.AsyncClient(transport=httpx.MockTransport(cancelled)) as client:
        provider = OpenAICompatibleGenerationProvider(
            descriptor(), base_url="https://models.example/v1", client=client
        )
        with pytest.raises(asyncio.CancelledError):
            await provider.complete(ModelRequest(prompt="text"))


def test_cloud_rejects_invalid_configuration() -> None:
    with pytest.raises(ValidationError):
        OpenAICompatibleGenerationProvider(descriptor(), base_url="not a URL")
    with pytest.raises(ValidationError):
        OpenAICompatibleGenerationProvider(
            descriptor(), base_url="https://models.example", timeout_seconds=61
        )
    with pytest.raises(ValidationError):
        OpenAICompatibleGenerationProvider(
            descriptor(), base_url="https://user:secret@models.example"
        )


class FakeLegacyModel:
    def __init__(self) -> None:
        self.calls: list[tuple[bytes | None, str, dict[str, Any]]] = []
        self.unloads = 0

    def process(self, image: bytes | None, prompt: str, **kwargs: Any) -> dict[str, Any]:
        self.calls.append((image, prompt, kwargs))
        return {"content": "read"}

    def unload(self) -> None:
        self.unloads += 1


@pytest.mark.asyncio
async def test_legacy_lazy_factory_loads_once_and_text_has_no_fake_image() -> None:
    model = FakeLegacyModel()
    factories: list[int] = []

    def load() -> FakeLegacyModel:
        factories.append(threading.get_ident())
        return model

    provider = LegacyVisionGenerationProvider(
        descriptor(supports_images=True), model_factory=load, supports_text=True
    )
    await asyncio.gather(*(provider.complete(ModelRequest(prompt="native text")) for _ in range(3)))
    assert len(factories) == 1
    assert factories[0] != threading.get_ident()
    assert all(call[0] is None for call in model.calls)
    await provider.aclose()
    await provider.aclose()
    assert model.unloads == 1


@pytest.mark.asyncio
async def test_legacy_text_support_is_explicit_and_preloaded_model_host_owned() -> None:
    model = FakeLegacyModel()
    provider = LegacyVisionGenerationProvider(descriptor(supports_images=True), model=model)
    assert not provider.descriptor.supports_text
    with pytest.raises(ExtractionError) as caught:
        await provider.complete(ModelRequest(prompt="text"))
    assert caught.value.code == "unsupported_model_features"
    assert not model.calls
    await provider.complete(ModelRequest(prompt="read", images=(image(),)))
    assert model.calls[0][0] == b"png"
    await provider.aclose()
    assert model.unloads == 0


def test_legacy_descriptor_does_not_claim_unimplemented_native_json() -> None:
    provider = LegacyVisionGenerationProvider(
        descriptor(supports_native_json=True), model=FakeLegacyModel()
    )
    assert not provider.descriptor.supports_native_json


@pytest.mark.asyncio
async def test_legacy_cancellation_does_not_release_running_thread_lease() -> None:
    started = threading.Event()
    release = threading.Event()
    calls: list[str] = []

    class BlockingModel(FakeLegacyModel):
        def process(self, image: bytes | None, prompt: str, **kwargs: Any) -> dict[str, Any]:
            calls.append(prompt)
            started.set()
            release.wait(3)
            return {"content": "read"}

    provider = LegacyVisionGenerationProvider(
        descriptor(), model=BlockingModel(), supports_text=True
    )
    first = asyncio.create_task(provider.complete(ModelRequest(prompt="first")))
    while not started.is_set():
        await asyncio.sleep(0.005)
    first.cancel()
    with pytest.raises(asyncio.CancelledError):
        await first
    second = asyncio.create_task(provider.complete(ModelRequest(prompt="second")))
    await asyncio.sleep(0.02)
    assert calls == ["first"]
    release.set()
    await second
    assert calls == ["first", "second"]
    await provider.aclose()


@pytest.mark.asyncio
async def test_legacy_timeout_defers_owned_model_unload_until_thread_finishes() -> None:
    release = threading.Event()
    started = threading.Event()

    class BlockingModel(FakeLegacyModel):
        def process(self, image: bytes | None, prompt: str, **kwargs: Any) -> dict[str, Any]:
            started.set()
            release.wait(3)
            return {"content": "read"}

    model = BlockingModel()
    provider = LegacyVisionGenerationProvider(
        descriptor(), model=model, supports_text=True, owns_model=True, timeout_seconds=0.02
    )
    with pytest.raises(ExtractionError) as caught:
        await provider.complete(ModelRequest(prompt="text"))
    assert caught.value.code == "model_timeout"
    assert started.is_set()
    closing = asyncio.create_task(provider.aclose())
    await asyncio.sleep(0.02)
    assert not closing.done()
    assert model.unloads == 0
    release.set()
    await closing
    assert model.unloads == 1


@pytest.mark.asyncio
async def test_legacy_failed_factory_is_not_repeated() -> None:
    calls: list[int] = []

    def load() -> FakeLegacyModel:
        calls.append(1)
        raise RuntimeError("credentials secret")

    provider = LegacyVisionGenerationProvider(descriptor(), model_factory=load, supports_text=True)
    for _ in range(2):
        with pytest.raises(ExtractionError) as caught:
            await provider.complete(ModelRequest(prompt="text"))
        assert caught.value.code == "provider_error"
        assert "secret" not in str(caught.value)
    assert calls == [1]
    await provider.aclose()


@pytest.mark.asyncio
async def test_legacy_error_dictionary_never_becomes_empty_success() -> None:
    model = FakeLegacyModel()
    model.process = lambda **kwargs: {"error": "private document and credentials"}
    provider = LegacyVisionGenerationProvider(descriptor(), model=model, supports_text=True)
    with pytest.raises(ExtractionError) as caught:
        await provider.complete(ModelRequest(prompt="text"))
    assert caught.value.code == "model_response_invalid"
    assert "private" not in str(caught.value)


@pytest.mark.asyncio
async def test_chat_adapter_uses_native_text_only_async_port() -> None:
    chat = AsyncMock()
    chat.complete.return_value = LLMResponse(
        content="fields", model="chat-model", finish_reason="stop"
    )
    provider = ChatGenerationProvider(chat, descriptor())
    output = await provider.complete(ModelRequest(prompt="text"))
    messages = chat.complete.await_args.args[0]
    assert messages[0].content == "text"
    assert output.content == "fields"
    with pytest.raises(ExtractionError) as caught:
        await provider.complete(ModelRequest(prompt="text", images=(image(),)))
    assert caught.value.code == "unsupported_model_features"
    assert chat.complete.await_count == 1


@pytest.mark.asyncio
async def test_cloud_closes_owned_client_and_rejects_reuse() -> None:
    provider = OpenAICompatibleGenerationProvider(
        descriptor(), base_url="https://models.example/v1"
    )
    await provider.aclose()
    await provider.aclose()
    assert provider._client.is_closed
    with pytest.raises(ExtractionError) as caught:
        await provider.complete(ModelRequest(prompt="text"))
    assert caught.value.code == "provider_error"
