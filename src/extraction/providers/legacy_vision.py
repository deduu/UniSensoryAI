"""Safe off-thread bridge for an injected synchronous vision model."""

import asyncio
import base64
from collections.abc import Callable
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field

from src.extraction.contracts import ModelDescriptor, ModelRequest, ModelResponse
from src.extraction.errors import ExtractionError
from src.extraction.ports.generation import BaseGenerationProvider
from src.extraction.usage import normalized_usage

from ._validation import normalize_response, validate_request


class _LegacyModel(Protocol):
    def process(self, image: bytes | None, prompt: str, **kwargs: Any) -> dict[str, Any]: ...

    def unload(self) -> None: ...


class _Settings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    supports_text: bool = False
    owns_model: bool
    timeout_seconds: float = Field(default=60, gt=0, le=60)


class LegacyVisionGenerationProvider(BaseGenerationProvider):
    """Adapt one preloaded model or lazy factory without global model imports.

    Local calls are serialized. Cancellation or timeout returns promptly, while
    the lock remains leased until the actual worker thread finishes. Shutdown
    waits for that lease before unloading an owned model.
    """

    def __init__(
        self,
        descriptor: ModelDescriptor,
        *,
        model: _LegacyModel | None = None,
        model_factory: Callable[[], _LegacyModel] | None = None,
        supports_text: bool = False,
        owns_model: bool | None = None,
        timeout_seconds: float = 60,
    ) -> None:
        """Configure model ownership and explicit native text support.

        Args:
            descriptor: Configured model features and prompt budget.
            model: A host-loaded model, host-owned by default.
            model_factory: An off-thread lazy factory, adapter-owned by default.
            supports_text: Host assertion that ``process(image=None)`` is valid.
            owns_model: Override default ownership for shutdown behavior.
            timeout_seconds: Maximum caller wait for an inference operation.
        """
        if (model is None) == (model_factory is None):
            raise ValueError("Supply exactly one model or model factory.")
        self._settings = _Settings(
            supports_text=supports_text,
            owns_model=(model_factory is not None) if owns_model is None else owns_model,
            timeout_seconds=timeout_seconds,
        )
        configured = ModelDescriptor.model_validate(descriptor)
        self._descriptor = configured.model_copy(
            update={
                "supports_text": self._settings.supports_text,
                "supports_native_json": False,
                "concurrency": 1,
                "max_images": min(configured.max_images, 1),
            }
        )
        self._model = model
        self._factory = model_factory
        self._load_attempted = model is not None
        self._lock = asyncio.Lock()
        self._pending: set[asyncio.Task[ModelResponse]] = set()
        self._closed = False

    @property
    def descriptor(self) -> ModelDescriptor:
        """Return conservative local limits without loading a model."""
        return self._descriptor

    def _run(self, request: ModelRequest) -> ModelResponse:
        if self._model is None:
            if self._load_attempted or self._factory is None:
                raise ExtractionError("provider_error", "The local model could not be loaded.")
            self._load_attempted = True
            self._model = self._factory()
        image_data = (
            base64.b64decode(request.images[0].data_base64, validate=True)
            if request.images
            else None
        )
        raw = self._model.process(
            image=image_data, prompt=request.prompt, max_tokens=request.max_output_tokens
        )
        if not isinstance(raw, dict) or raw.get("error"):
            raise ExtractionError(
                "model_response_invalid",
                "The local model returned a failure.",
                usage=normalized_usage(raw.get("usage")) if isinstance(raw, dict) else None,
            )
        metadata = raw.get("raw_response")
        if not isinstance(metadata, dict):
            metadata = {}
        finish_reason = raw.get("finish_reason")
        choices = metadata.get("choices")
        if (
            finish_reason is None
            and isinstance(choices, list)
            and choices
            and isinstance(choices[0], dict)
        ):
            finish_reason = choices[0].get("finish_reason")
        return normalize_response(
            raw.get("content"),
            self.descriptor.model_id,
            finish_reason,
            raw.get("usage", metadata.get("usage")),
        )

    def _release_background(self, task: asyncio.Task[ModelResponse]) -> None:
        self._pending.discard(task)
        if not task.cancelled():
            task.exception()
        self._lock.release()

    async def complete(self, request: ModelRequest) -> ModelResponse:
        """Execute off-thread while retaining the lease after caller cancellation."""
        request = ModelRequest.model_validate(request)
        validate_request(self.descriptor, request)
        await self._lock.acquire()
        if self._closed:
            self._lock.release()
            raise ExtractionError("provider_error", "The local model provider has been closed.")
        task = asyncio.create_task(asyncio.to_thread(self._run, request))
        deferred_release = False
        try:
            return await asyncio.wait_for(
                asyncio.shield(task), timeout=self._settings.timeout_seconds
            )
        except asyncio.CancelledError:
            deferred_release = True
            self._pending.add(task)
            task.add_done_callback(self._release_background)
            raise
        except asyncio.TimeoutError:
            deferred_release = True
            self._pending.add(task)
            task.add_done_callback(self._release_background)
            raise ExtractionError("model_timeout", "The local model request timed out.") from None
        except ExtractionError:
            raise
        except Exception:  # noqa: BLE001 - Normalize failures from arbitrary host models.
            raise ExtractionError(
                "provider_error", "The local model failed to complete the request."
            ) from None
        finally:
            if not deferred_release:
                self._lock.release()

    async def aclose(self) -> None:
        """Wait for active inference and unload an adapter-owned model once."""
        async with self._lock:
            if self._closed:
                return
            self._closed = True
            model = self._model
            self._model = None
            if self._settings.owns_model and model is not None:
                try:
                    await asyncio.to_thread(model.unload)
                except Exception:  # noqa: BLE001 - Keep model cleanup failures sanitized.
                    raise ExtractionError(
                        "provider_error", "The local model could not be closed."
                    ) from None
