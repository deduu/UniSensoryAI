"""Tests for the ``LLMProvider`` ABC and the OpenAI-compatible client.

The ``OpenAICompatibleClient`` talks to any chat-completions API
(OpenAI, Together, Fireworks, OpenRouter, ...). Tests mock the HTTP
transport so they stay offline.
"""

from __future__ import annotations

import json

import httpx
import pytest

from src.orchestration.llm.base import LLMMessage, LLMProvider, LLMResponse
from src.orchestration.llm.mock import MockLLMProvider
from src.orchestration.llm.openai_compat import OpenAICompatibleClient


# ---------------------------------------------------------------------------
# ABC contract
# ---------------------------------------------------------------------------


def test_llm_provider_abc_rejects_incomplete_subclass() -> None:
    class Half(LLMProvider):
        pass

    with pytest.raises(TypeError):
        Half()  # type: ignore[abstract]


@pytest.mark.asyncio
async def test_mock_llm_provider_returns_canned_responses_in_order() -> None:
    mock = MockLLMProvider(responses=["first", "second"])
    a = await mock.complete([LLMMessage(role="user", content="x")])
    b = await mock.complete([LLMMessage(role="user", content="y")])
    assert a.content == "first"
    assert b.content == "second"
    assert mock.call_count == 2


@pytest.mark.asyncio
async def test_mock_llm_provider_records_messages() -> None:
    mock = MockLLMProvider(responses=["ok"])
    msgs = [LLMMessage(role="user", content="hi")]
    await mock.complete(msgs)
    assert mock.calls == [msgs]


@pytest.mark.asyncio
async def test_mock_llm_provider_raises_when_exhausted() -> None:
    mock = MockLLMProvider(responses=["only one"])
    await mock.complete([LLMMessage(role="user", content="x")])
    with pytest.raises(IndexError):
        await mock.complete([LLMMessage(role="user", content="y")])


# ---------------------------------------------------------------------------
# OpenAI-compatible client
# ---------------------------------------------------------------------------


_OPENAI_BODY = {
    "id": "chatcmpl-1",
    "object": "chat.completion",
    "model": "gpt-4o",
    "choices": [
        {
            "index": 0,
            "message": {"role": "assistant", "content": "Hi there."},
            "finish_reason": "stop",
        }
    ],
    "usage": {"prompt_tokens": 4, "completion_tokens": 3, "total_tokens": 7},
}


@pytest.mark.asyncio
async def test_openai_client_sends_correct_request_and_parses_response() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, content=json.dumps(_OPENAI_BODY).encode())

    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport)
    llm = OpenAICompatibleClient(
        api_key="test-key",
        base_url="https://api.openai.com/v1",
        model="gpt-4o",
        client=client,
    )

    response = await llm.complete(
        [LLMMessage(role="user", content="hi")],
        temperature=0.3,
    )

    assert isinstance(response, LLMResponse)
    assert response.content == "Hi there."
    assert response.model == "gpt-4o"
    assert response.token_usage == {
        "prompt_tokens": 4,
        "completion_tokens": 3,
        "total_tokens": 7,
    }
    sent = captured[0]
    assert sent.method == "POST"
    assert sent.url.path.endswith("/chat/completions")
    assert sent.headers["Authorization"] == "Bearer test-key"
    payload = json.loads(sent.content.decode())
    assert payload["model"] == "gpt-4o"
    assert payload["temperature"] == 0.3
    assert payload["messages"] == [{"role": "user", "content": "hi"}]
    assert payload["stream"] is False
    await client.aclose()


@pytest.mark.asyncio
async def test_openai_client_honours_response_format() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, content=json.dumps(_OPENAI_BODY).encode())

    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport)
    llm = OpenAICompatibleClient(
        api_key="k", base_url="https://x.test/v1", model="m", client=client
    )

    await llm.complete(
        [LLMMessage(role="user", content="hi")],
        response_format={"type": "json_object"},
    )

    payload = json.loads(captured[0].content.decode())
    assert payload["response_format"] == {"type": "json_object"}
    await client.aclose()


@pytest.mark.asyncio
async def test_openai_client_raises_on_http_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, content=b"oops")

    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport)
    llm = OpenAICompatibleClient(
        api_key="k", base_url="https://x.test/v1", model="m", client=client
    )
    with pytest.raises(httpx.HTTPStatusError):
        await llm.complete([LLMMessage(role="user", content="hi")])
    await client.aclose()


def test_openai_client_requires_api_key() -> None:
    with pytest.raises(ValueError, match="api_key"):
        OpenAICompatibleClient(api_key="", base_url="https://x.test/v1", model="m")
