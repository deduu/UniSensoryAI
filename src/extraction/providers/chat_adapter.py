"""Reuse an existing async chat provider through the generation port."""

import asyncio
from typing import Any

from src.extraction.contracts import ModelDescriptor, ModelRequest, ModelResponse
from src.extraction.errors import ExtractionError
from src.extraction.ports.generation import BaseGenerationProvider
from src.extraction.usage import normalized_usage
from src.orchestration.llm.base import LLMMessage, LLMProvider

from ._validation import normalize_response, validate_request


class ChatGenerationProvider(BaseGenerationProvider):
    """Bridge the existing text-only chat interface without changing chat workflows."""

    def __init__(self, provider: LLMProvider, descriptor: ModelDescriptor) -> None:
        """Inject a host-owned async provider and explicit model features.

        Args:
            provider: Existing provider supporting async chat completions.
            descriptor: Text model identity and input limits.
        """
        self._provider = provider
        configured = ModelDescriptor.model_validate(descriptor)
        self._descriptor = configured.model_copy(
            update={"supports_text": True, "supports_images": False, "max_images": 0}
        )

    @property
    def descriptor(self) -> ModelDescriptor:
        """Describe the text-only bridge without contacting its provider."""
        return self._descriptor

    async def complete(self, request: ModelRequest) -> ModelResponse:
        """Forward text and supported native schemas through the async chat port."""
        request = ModelRequest.model_validate(request)
        validate_request(self.descriptor, request)
        response_format: dict[str, Any] | None = None
        if request.json_schema is not None and self.descriptor.supports_native_json:
            response_format = {
                "type": "json_schema",
                "json_schema": {
                    "name": "extraction_result",
                    "schema": request.json_schema,
                    "strict": False,
                },
            }
        try:
            response = await asyncio.wait_for(
                self._provider.complete(
                    [LLMMessage(role="user", content=request.prompt)],
                    temperature=0,
                    max_tokens=request.max_output_tokens,
                    response_format=response_format,
                ),
                timeout=60,
            )
            return normalize_response(
                response.content,
                self.descriptor.model_id,
                response.finish_reason,
                {**normalized_usage(response.raw.get("usage")), **response.token_usage},
                response_model_id=response.model,
            )
        except asyncio.CancelledError:
            raise
        except asyncio.TimeoutError:
            raise ExtractionError("model_timeout", "The model request timed out.") from None
        except ExtractionError:
            raise
        except Exception:  # noqa: BLE001 - Do not expose provider payloads or credentials.
            raise ExtractionError(
                "provider_error", "The model provider failed to complete the request."
            ) from None
