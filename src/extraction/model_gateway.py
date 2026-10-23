"""Model-neutral routing with bounded concurrency, timeout, and call rate."""

import asyncio
import time
from collections import deque
from collections.abc import Mapping

from pydantic import BaseModel, ConfigDict, Field

from src.extraction.contracts import ModelDescriptor, ModelRequest, ModelResponse
from src.extraction.contracts.usage import ModelPricing
from src.extraction.errors import ExtractionError
from src.extraction.ports.gateway import BaseModelGateway
from src.extraction.ports.generation import BaseGenerationProvider
from src.extraction.providers._validation import normalize_response, validate_request
from src.extraction.usage import active_usage_collector

_SAFE_PROVIDER_CODES = frozenset(
    {
        "context_limit",
        "unsupported_model_features",
        "model_response_invalid",
        "model_timeout",
        "provider_error",
    }
)


class _Settings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    calls_per_second: int = Field(default=10, ge=1, le=10)
    timeout_seconds: float = Field(default=60, gt=0, le=60)


class ModelGateway(BaseModelGateway):
    """Resolve host-defined profiles to injected generation providers.

    A single gateway applies one rolling-window rate limit across its profiles.
    Aliases of the same provider share a semaphore. Providers remain host-owned;
    the host closes them after all workflows using this gateway finish.
    """

    def __init__(
        self,
        providers: Mapping[str, BaseGenerationProvider],
        *,
        calls_per_second: int = 10,
        timeout_seconds: float = 60,
        pricing: Mapping[str, ModelPricing] | None = None,
        provider_names: Mapping[str, str] | None = None,
    ) -> None:
        """Configure profiles and operating limits without loading models.

        Args:
            providers: Logical profile names mapped to provider instances.
            calls_per_second: Maximum call starts in each one-second window.
            timeout_seconds: Maximum wait including scheduling and inference.
            pricing: Optional host-provided per-profile model-bound price snapshots.
            provider_names: Safe factory identities; no endpoint or credentials.
        """
        self._settings = _Settings(
            calls_per_second=calls_per_second, timeout_seconds=timeout_seconds
        )
        self._providers = dict(providers)
        if any(
            not isinstance(name, str)
            or not name.strip()
            or not isinstance(provider, BaseGenerationProvider)
            for name, provider in self._providers.items()
        ):
            raise ValueError("Model profiles require nonempty names and generation providers.")
        self._semaphores = {
            id(provider): asyncio.Semaphore(provider.descriptor.concurrency)
            for provider in self._providers.values()
        }
        self._rate_lock = asyncio.Lock()
        self._starts: deque[float] = deque()
        self._pricing = {
            name: ModelPricing.model_validate(rate) for name, rate in (pricing or {}).items()
        }
        if any(
            name not in self._providers
            or rate.model_id != self._providers[name].descriptor.model_id
            for name, rate in self._pricing.items()
        ):
            raise ValueError("Pricing must bind to its configured profile and exact model.")
        self._provider_names = {
            name: (provider_names or {}).get(name, type(provider).__name__)
            for name, provider in self._providers.items()
        }

    def _provider(self, profile: str) -> BaseGenerationProvider:
        provider = self._providers.get(profile)
        if provider is None:
            raise ExtractionError("unknown_model_profile", "The model profile is not configured.")
        return provider

    def describe(self, profile: str) -> ModelDescriptor:
        """Describe a profile without instantiating or loading its model."""
        return self._provider(profile).descriptor

    async def _wait_for_rate_slot(self) -> None:
        while True:
            async with self._rate_lock:
                now = time.monotonic()
                while self._starts and now - self._starts[0] >= 1.0:
                    self._starts.popleft()
                if len(self._starts) < self._settings.calls_per_second:
                    self._starts.append(now)
                    return
                delay = 1.0 - (now - self._starts[0])
            await asyncio.sleep(delay)

    async def _call(
        self, profile: str, provider: BaseGenerationProvider, request: ModelRequest
    ) -> ModelResponse:
        async with self._semaphores[id(provider)]:
            await self._wait_for_rate_slot()
            collector = active_usage_collector()
            index = (
                collector.begin(
                    profile=profile,
                    provider=self._provider_names[profile],
                    model_id=provider.descriptor.model_id,
                    purpose=request.purpose,
                    pricing=self._pricing.get(profile),
                )
                if collector is not None
                else None
            )
            try:
                response = await provider.complete(request)
                if not isinstance(response, ModelResponse):
                    raise ExtractionError(
                        "model_response_invalid", "The provider returned an invalid response."
                    )
                response = normalize_response(
                    response.content,
                    response.model_id,
                    response.finish_reason,
                    response.usage,
                    response_model_id=response.response_model_id,
                )
            except asyncio.CancelledError:
                if collector is not None and index is not None:
                    collector.finish(index, status="cancelled", error_code="cancelled")
                raise
            except Exception as exc:
                if collector is not None and index is not None:
                    code = exc.code if isinstance(exc, ExtractionError) else "provider_error"
                    collector.finish(
                        index,
                        status="failed",
                        usage=exc.usage if isinstance(exc, ExtractionError) else None,
                        response_model_id=(
                            exc.response_model_id if isinstance(exc, ExtractionError) else None
                        ),
                        error_code=code if code in _SAFE_PROVIDER_CODES else "provider_error",
                    )
                raise
            if collector is not None and index is not None:
                collector.finish(
                    index,
                    status="succeeded",
                    usage=response.usage,
                    model_id=response.model_id,
                    response_model_id=response.response_model_id,
                )
            return response

    async def generate(self, profile: str, request: ModelRequest) -> ModelResponse:
        """Validate compatibility and perform a bounded, sanitized model call."""
        provider = self._provider(profile)
        request = ModelRequest.model_validate(request)
        validate_request(provider.descriptor, request)
        try:
            return await asyncio.wait_for(
                self._call(profile, provider, request), timeout=self._settings.timeout_seconds
            )
        except asyncio.CancelledError:
            raise
        except asyncio.TimeoutError:
            raise ExtractionError("model_timeout", "The model request timed out.") from None
        except ExtractionError as exc:
            messages = {
                "context_limit": "The model input exceeds its configured limit.",
                "unsupported_model_features": "The model does not support the requested inputs.",
                "model_response_invalid": "The model returned an invalid or incomplete response.",
                "model_timeout": "The model request timed out.",
                "provider_error": "The model provider failed to complete the request.",
            }
            code = exc.code if exc.code in messages else "provider_error"
            raise ExtractionError(
                code, messages[code], usage=exc.usage, response_model_id=exc.response_model_id
            ) from None
        except Exception:  # noqa: BLE001 - Normalize failures from arbitrary injected providers.
            raise ExtractionError(
                "provider_error", "The model provider failed to complete the request."
            ) from None
