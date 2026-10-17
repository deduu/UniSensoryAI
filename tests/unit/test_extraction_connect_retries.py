"""Only failed connection establishment retries within one inference deadline."""

import asyncio
import json
import ssl
from pathlib import Path
from typing import Any

import httpcore
import httpx
import pytest
from httpcore._backends.auto import AutoBackend
from pydantic import ValidationError

from src.extraction.composition import build_extraction_service
from src.extraction.contracts import ModelDescriptor, ModelRequest
from src.extraction.errors import ExtractionError
from src.extraction.provider_profile import ProviderProfile
from src.extraction.providers import OpenAICompatibleGenerationProvider


class _HTTPStream(httpcore.AsyncNetworkStream):
    def __init__(self, status: int = 200, *, body: dict[str, Any] | None = None) -> None:
        payload = json.dumps(
            body
            if body is not None
            else {"choices": [{"message": {"content": "complete"}, "finish_reason": "stop"}]}
        ).encode()
        self._response = (
            f"HTTP/1.1 {status} Test\r\nContent-Length: {len(payload)}\r\nConnection: close\r\n\r\n".encode()
            + payload
        )
        self.writes: list[bytes] = []

    async def read(self, max_bytes: int, timeout: float | None = None) -> bytes:
        response, self._response = self._response, b""
        return response

    async def write(self, buffer: bytes, timeout: float | None = None) -> None:
        self.writes.append(buffer)

    async def aclose(self) -> None:
        pass

    async def start_tls(
        self,
        ssl_context: ssl.SSLContext,
        server_hostname: str | None = None,
        timeout: float | None = None,
    ) -> httpcore.AsyncNetworkStream:
        return self

    def get_extra_info(self, info: str) -> Any:
        return None


@pytest.mark.asyncio
async def test_transient_connection_error_retries_before_any_request_is_transmitted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0
    stream = _HTTPStream()

    async def connect(*args: Any, **kwargs: Any) -> httpcore.AsyncNetworkStream:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise httpcore.ConnectError("private DNS details")
        return stream

    monkeypatch.setattr(AutoBackend, "connect_tcp", connect)
    provider = OpenAICompatibleGenerationProvider(
        ModelDescriptor(model_id="host"), base_url="https://models.example/v1", connect_retries=2
    )
    try:
        result = await provider.complete(ModelRequest(prompt="source"))
        assert result.content == "complete"
        assert calls == 2
        assert b"".join(stream.writes).count(b"POST /v1/chat/completions") == 1
    finally:
        await provider.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize("budget", [0, 1, 3])
@pytest.mark.parametrize(
    "failure,code",
    [(httpcore.ConnectError, "provider_error"), (httpcore.ConnectTimeout, "model_timeout")],
)
async def test_connect_retry_budget_is_bounded_and_failure_details_are_safe(
    monkeypatch: pytest.MonkeyPatch,
    failure: type[Exception],
    code: str,
    budget: int,
) -> None:
    calls = 0

    async def connect(*args: Any, **kwargs: Any) -> httpcore.AsyncNetworkStream:
        nonlocal calls
        calls += 1
        raise failure("private endpoint and credentials")

    monkeypatch.setattr(AutoBackend, "connect_tcp", connect)
    provider = OpenAICompatibleGenerationProvider(
        ModelDescriptor(model_id="host"),
        base_url="https://models.example/v1",
        connect_retries=budget,
    )
    try:
        with pytest.raises(ExtractionError) as caught:
            await provider.complete(ModelRequest(prompt="source"))
        assert caught.value.code == code
        assert "private" not in str(caught.value)
        assert calls == budget + 1
    finally:
        await provider.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status,body,code",
    [
        (429, None, "provider_error"),
        (500, None, "provider_error"),
        (200, {"choices": []}, "model_response_invalid"),
    ],
)
async def test_http_status_and_model_response_are_never_retried(
    monkeypatch: pytest.MonkeyPatch,
    status: int,
    body: dict[str, Any] | None,
    code: str,
) -> None:
    calls = 0

    async def connect(*args: Any, **kwargs: Any) -> httpcore.AsyncNetworkStream:
        nonlocal calls
        calls += 1
        return _HTTPStream(status, body=body)

    monkeypatch.setattr(AutoBackend, "connect_tcp", connect)
    provider = OpenAICompatibleGenerationProvider(
        ModelDescriptor(model_id="host"), base_url="https://models.example/v1", connect_retries=3
    )
    try:
        with pytest.raises(ExtractionError) as caught:
            await provider.complete(ModelRequest(prompt="source"))
        assert caught.value.code == code
        assert calls == 1
    finally:
        await provider.aclose()


@pytest.mark.asyncio
async def test_retries_share_one_total_inference_deadline(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0
    cancelled = asyncio.Event()

    async def connect(*args: Any, **kwargs: Any) -> httpcore.AsyncNetworkStream:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise httpcore.ConnectError("transient")
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()
        return _HTTPStream()

    monkeypatch.setattr(AutoBackend, "connect_tcp", connect)
    provider = OpenAICompatibleGenerationProvider(
        ModelDescriptor(model_id="host"),
        base_url="https://models.example/v1",
        connect_retries=3,
        timeout_seconds=0.03,
    )
    try:
        with pytest.raises(ExtractionError) as caught:
            await provider.complete(ModelRequest(prompt="source"))
        assert caught.value.code == "model_timeout"
        assert calls == 2
        assert cancelled.is_set()
    finally:
        await provider.aclose()


@pytest.mark.asyncio
async def test_injected_client_keeps_its_transport_and_ownership() -> None:
    calls = 0

    async def handle(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.ConnectError("private", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
        provider = OpenAICompatibleGenerationProvider(
            ModelDescriptor(model_id="host"),
            base_url="https://models.example/v1",
            client=client,
            connect_retries=3,
        )
        with pytest.raises(ExtractionError):
            await provider.complete(ModelRequest(prompt="source"))
        await provider.aclose()
        assert calls == 1
        assert not client.is_closed


@pytest.mark.asyncio
async def test_response_read_failure_does_not_replay_a_transmitted_model_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0
    stream = _HTTPStream()

    async def failed_read(max_bytes: int, timeout: float | None = None) -> bytes:
        raise httpcore.ReadError("private response details")

    async def connect(*args: Any, **kwargs: Any) -> httpcore.AsyncNetworkStream:
        nonlocal calls
        calls += 1
        return stream

    monkeypatch.setattr(stream, "read", failed_read)
    monkeypatch.setattr(AutoBackend, "connect_tcp", connect)
    provider = OpenAICompatibleGenerationProvider(
        ModelDescriptor(model_id="host"), base_url="https://models.example/v1", connect_retries=3
    )
    try:
        with pytest.raises(ExtractionError) as caught:
            await provider.complete(ModelRequest(prompt="source"))
        assert caught.value.code == "provider_error"
        assert calls == 1
        assert b"".join(stream.writes).count(b"POST /v1/chat/completions") == 1
    finally:
        await provider.aclose()


@pytest.mark.parametrize("budget", [-1, 4])
def test_connection_retry_inputs_are_validated(budget: int) -> None:
    with pytest.raises(ValidationError):
        ProviderProfile(model_id="host", connect_retries=budget)
    with pytest.raises(ValidationError):
        OpenAICompatibleGenerationProvider(
            ModelDescriptor(model_id="host"),
            base_url="https://models.example/v1",
            connect_retries=budget,
        )


@pytest.mark.asyncio
async def test_composition_passes_the_deployment_connection_retry_budget(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.extraction import composition

    recorded: list[int] = []
    original = composition.OpenAICompatibleGenerationProvider

    def construct(*args: Any, **kwargs: Any) -> OpenAICompatibleGenerationProvider:
        recorded.append(kwargs.get("connect_retries", -1))
        return original(*args, **kwargs)

    monkeypatch.setattr(composition, "OpenAICompatibleGenerationProvider", construct)
    config = tmp_path / "extraction.yaml"
    config.write_text(
        "profiles:\n  vision:\n    model_id: host\n    base_url: https://models.example/v1\n    connect_retries: 2\n",
        encoding="utf-8",
    )
    service = await build_extraction_service(config_path=config)
    try:
        assert recorded == [2]
    finally:
        await service.aclose()
