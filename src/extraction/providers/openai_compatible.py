"""Native async adapter for configured OpenAI-compatible generation APIs."""

import asyncio
from typing import Any

import httpx
from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, SecretStr, field_validator

from src.extraction.contracts import ModelDescriptor, ModelRequest, ModelResponse
from src.extraction.errors import ExtractionError
from src.extraction.ports.generation import BaseGenerationProvider

from ._validation import normalize_response, validate_request


class _Settings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    base_url: AnyHttpUrl
    api_key: SecretStr | None = None
    timeout_seconds: float = Field(default=60, gt=0, le=60)
    connect_retries: int = Field(default=0, ge=0, le=3)

    @field_validator("base_url")
    @classmethod
    def _reject_url_credentials(cls, value: AnyHttpUrl) -> AnyHttpUrl:
        if value.username or value.password or value.query or value.fragment:
            raise ValueError("The model endpoint must not contain credentials or query parameters.")
        return value


class OpenAICompatibleGenerationProvider(BaseGenerationProvider):
    """Translate neutral requests into text or multimodal chat completions."""

    def __init__(
        self,
        descriptor: ModelDescriptor,
        *,
        base_url: str,
        api_key: str | None = None,
        client: httpx.AsyncClient | None = None,
        timeout_seconds: float = 60,
        connect_retries: int = 0,
    ) -> None:
        """Configure an adapter without making any network request.

        Args:
            descriptor: Configured model identity, supported features, and limits.
            base_url: API base ending at the version prefix, such as ``/v1``.
            api_key: Optional secret, held only in private validated settings.
            client: Optional host-owned async client.
            timeout_seconds: Maximum elapsed duration of one inference call.
            connect_retries: Bounded connection-establishment retries for an owned client.
                An injected client's transport and retry policy remain host-owned.
        """
        self._descriptor = ModelDescriptor.model_validate(descriptor)
        self._settings = _Settings.model_validate(
            {
                "base_url": base_url,
                "api_key": api_key,
                "timeout_seconds": timeout_seconds,
                "connect_retries": connect_retries,
            }
        )
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            timeout=self._settings.timeout_seconds,
            transport=(
                httpx.AsyncHTTPTransport(retries=self._settings.connect_retries)
                if self._settings.connect_retries
                else None
            ),
        )
        self._closed = False

    @property
    def descriptor(self) -> ModelDescriptor:
        """Return configured features without contacting the provider."""
        return self._descriptor

    def _payload(self, request: ModelRequest) -> dict[str, Any]:
        content: str | list[dict[str, Any]] = request.prompt
        if request.images:
            content = [{"type": "text", "text": request.prompt}]
            content.extend(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{asset.media_type};base64,{asset.data_base64}"},
                }
                for asset in request.images
            )
        payload: dict[str, Any] = {
            "model": self.descriptor.model_id,
            "messages": [{"role": "user", "content": content}],
            "max_tokens": request.max_output_tokens,
        }
        if request.json_schema is not None and self.descriptor.supports_native_json:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "extraction_result",
                    "schema": request.json_schema,
                    "strict": False,
                },
            }
        return payload

    async def _send(self, request: ModelRequest) -> ModelResponse:
        headers = {}
        if self._settings.api_key is not None:
            headers["Authorization"] = f"Bearer {self._settings.api_key.get_secret_value()}"
        url = f"{str(self._settings.base_url).rstrip('/')}/chat/completions"
        response = await self._client.post(url, headers=headers, json=self._payload(request))
        response.raise_for_status()
        try:
            body = response.json()
            if not isinstance(body, dict) or body.get("error"):
                raise ValueError
            choice = body["choices"][0]
            message = choice["message"]
            if message.get("refusal"):
                raise ValueError
            return normalize_response(
                message.get("content"),
                self.descriptor.model_id,
                choice.get("finish_reason"),
                body.get("usage"),
            )
        except ExtractionError:
            raise
        except (ValueError, KeyError, IndexError, TypeError, AttributeError):
            raise ExtractionError(
                "model_response_invalid", "The model returned an invalid response."
            ) from None

    async def complete(self, request: ModelRequest) -> ModelResponse:
        """Run real text-only or image inference without a placeholder image."""
        request = ModelRequest.model_validate(request)
        validate_request(self.descriptor, request)
        if self._closed:
            raise ExtractionError("provider_error", "The model provider has been closed.")
        try:
            return await asyncio.wait_for(
                self._send(request), timeout=self._settings.timeout_seconds
            )
        except asyncio.CancelledError:
            raise
        except (asyncio.TimeoutError, httpx.TimeoutException):
            raise ExtractionError("model_timeout", "The model request timed out.") from None
        except ExtractionError:
            raise
        except Exception:  # noqa: BLE001 - Do not expose provider payloads or credentials.
            raise ExtractionError(
                "provider_error", "The model provider failed to complete the request."
            ) from None

    async def aclose(self) -> None:
        """Close an adapter-owned client; an injected client remains host-owned."""
        if self._closed:
            return
        self._closed = True
        if self._owns_client:
            await self._client.aclose()
