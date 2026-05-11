"""OpenAI-compatible chat-completions client.

Works with OpenAI, Together AI, Fireworks, OpenRouter, DeepInfra, and any
other provider that speaks the OpenAI chat-completions HTTP shape.
"""

from __future__ import annotations

from typing import Any

import httpx

from src.orchestration.llm.base import LLMMessage, LLMProvider, LLMResponse


class OpenAICompatibleClient(LLMProvider):
    """Talks to any OpenAI-compatible ``/v1/chat/completions`` endpoint.

    Args:
        api_key: Bearer token for the provider.
        base_url: API root, e.g. ``https://api.openai.com/v1``. Trailing
            ``/`` is stripped.
        model: Model identifier sent in every request.
        timeout_seconds: Per-request timeout (capped at the 60s LLM budget
            from CLAUDE.md rule 9).
        default_max_tokens: Used when the caller doesn't supply one.
        client: Optional pre-built ``httpx.AsyncClient``; not closed by
            this class when supplied.
    """

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        timeout_seconds: float = 60.0,
        default_max_tokens: int | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("OpenAICompatibleClient requires a non-empty api_key")
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout = timeout_seconds
        self._default_max_tokens = default_max_tokens
        self._client = client

    @property
    def model(self) -> str:
        return self._model

    async def complete(
        self,
        messages: list[LLMMessage],
        *,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        response_format: dict[str, Any] | None = None,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
    ) -> LLMResponse:
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": [self._serialize(m) for m in messages],
            "temperature": temperature,
            "stream": False,
        }
        token_budget = max_tokens if max_tokens is not None else self._default_max_tokens
        if token_budget is not None:
            payload["max_tokens"] = token_budget
        if response_format is not None:
            payload["response_format"] = response_format
        if tools is not None:
            payload["tools"] = tools
        if tool_choice is not None:
            payload["tool_choice"] = tool_choice

        owned = self._client is None
        client = self._client or httpx.AsyncClient(timeout=self._timeout)
        try:
            response = await client.post(
                f"{self._base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
        finally:
            if owned:
                await client.aclose()

        choice = (data.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        return LLMResponse(
            content=message.get("content") or "",
            model=data.get("model") or self._model,
            finish_reason=choice.get("finish_reason"),
            token_usage=data.get("usage") or {},
            raw=data,
        )

    @staticmethod
    def _serialize(message: LLMMessage) -> dict[str, Any]:
        payload: dict[str, Any] = {"role": message.role, "content": message.content}
        if message.name:
            payload["name"] = message.name
        if message.tool_call_id:
            payload["tool_call_id"] = message.tool_call_id
        return payload
