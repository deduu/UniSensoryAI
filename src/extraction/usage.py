"""Request-scoped model usage accounting without global job state or I/O."""

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from decimal import Decimal
from typing import Literal

from .contracts.model_usage_call import ModelUsageCall
from .contracts.usage import ExtractionUsage, ModelPricing

_ACTIVE: ContextVar["UsageCollector | None"] = ContextVar("extraction_usage", default=None)
_MILLION = Decimal(1_000_000)


def normalized_usage(usage: object) -> dict[str, int]:
    """Keep safe integer counters and flatten recognized cached-token details.

    No prompt, provider response body, URL or credential enters the ledger.
    Unknown top-level integer counters remain compatible with ModelResponse.
    """
    if not isinstance(usage, Mapping):
        return {}
    counters = {
        key: value
        for key, value in usage.items()
        if isinstance(key, str)
        and isinstance(value, int)
        and not isinstance(value, bool)
        and value >= 0
    }
    if "cached_input_tokens" not in counters:
        for key in ("prompt_tokens_details", "input_tokens_details"):
            detail = usage.get(key)
            cached = detail.get("cached_tokens") if isinstance(detail, Mapping) else None
            if isinstance(cached, int) and not isinstance(cached, bool) and cached >= 0:
                counters["cached_input_tokens"] = cached
                break
    return counters


def _count(counters: Mapping[str, int], *keys: str) -> int | None:
    return next((counters[key] for key in keys if key in counters), None)


def _cost(
    pricing: ModelPricing | None,
    model_id: str,
    input_tokens: int | None,
    output_tokens: int | None,
    cached: int | None,
    response_model_id: str | None,
) -> Decimal | None:
    if (
        pricing is None
        or pricing.model_id != model_id
        or (
            response_model_id is not None
            and response_model_id != pricing.model_id
            and response_model_id not in pricing.allowed_response_model_ids
        )
        or input_tokens is None
        or output_tokens is None
        or (cached is not None and cached > input_tokens)
    ):
        return None
    if pricing.cached_input_per_million is not None:
        if cached is None:
            return None
        return (
            Decimal(input_tokens - cached) * pricing.input_per_million
            + Decimal(cached) * pricing.cached_input_per_million
            + Decimal(output_tokens) * pricing.output_per_million
        ) / _MILLION
    return (
        Decimal(input_tokens) * pricing.input_per_million
        + Decimal(output_tokens) * pricing.output_per_million
    ) / _MILLION


def _coverage(known: int, total: int) -> Literal["complete", "partial", "unavailable"]:
    if known == total:
        return "complete"
    return "partial" if known else "unavailable"


class UsageCollector:
    """Accumulate safe completed/in-flight calls in one explicitly scoped run."""

    def __init__(self, previous: ExtractionUsage | None = None) -> None:
        """Create an empty collector; no providers or prices are discovered."""
        self._calls = list(ExtractionUsage.model_validate(previous).calls) if previous else []

    def begin(
        self,
        *,
        profile: str,
        provider: str,
        model_id: str,
        purpose: Literal["ocr", "vision", "fields"],
        pricing: ModelPricing | None,
    ) -> int:
        """Record an invocation immediately before it enters its provider."""
        index = len(self._calls)
        self._calls.append(
            ModelUsageCall(
                sequence=index + 1,
                profile=profile,
                provider=provider,
                model_id=model_id,
                purpose=purpose,
                status="failed",
                pricing=pricing,
                currency=pricing.currency if pricing else None,
                error_code="usage_pending",
            )
        )
        return index

    def finish(
        self,
        index: int,
        *,
        status: Literal["succeeded", "failed", "cancelled"],
        usage: object = None,
        model_id: str | None = None,
        response_model_id: str | None = None,
        error_code: str | None = None,
    ) -> None:
        """Close an attempted call, retaining unknown counters as null."""
        call = self._calls[index]
        counters = normalized_usage(usage)
        input_tokens = _count(counters, "input_tokens", "prompt_tokens")
        output_tokens = _count(counters, "output_tokens", "completion_tokens")
        total_tokens = _count(counters, "total_tokens")
        if total_tokens is None and input_tokens is not None and output_tokens is not None:
            total_tokens = input_tokens + output_tokens
        cached = _count(counters, "cached_input_tokens")
        resolved_model = model_id or call.model_id
        self._calls[index] = ModelUsageCall.model_validate(
            {
                **call.model_dump(),
                "status": status,
                "model_id": resolved_model,
                "response_model_id": response_model_id,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": total_tokens,
                "cached_input_tokens": cached,
                "estimated_cost": _cost(
                    call.pricing,
                    resolved_model,
                    input_tokens,
                    output_tokens,
                    cached,
                    response_model_id,
                ),
                "error_code": error_code,
            }
        )

    def snapshot(self) -> ExtractionUsage:
        """Return an immutable snapshot with honest token and price coverage."""
        calls = tuple(self._calls)
        measured = sum(
            call.input_tokens is not None
            and call.output_tokens is not None
            and call.total_tokens is not None
            and call.input_tokens + call.output_tokens == call.total_tokens
            for call in calls
        )

        def subtotal(attribute: str) -> int | None:
            values = [getattr(call, attribute) for call in calls]
            known = [value for value in values if value is not None]
            return sum(known) if known or not calls else None

        priced = [call for call in calls if call.estimated_cost is not None]
        currencies = {call.currency for call in priced}
        one_currency = len(currencies) == 1
        cost_coverage = _coverage(len(priced), len(calls)) if calls else "unavailable"
        if priced and not one_currency:
            cost_coverage = "partial"
        return ExtractionUsage(
            calls=calls,
            call_count=len(calls),
            measured_call_count=measured,
            input_tokens=subtotal("input_tokens"),
            output_tokens=subtotal("output_tokens"),
            total_tokens=subtotal("total_tokens"),
            estimated_cost=(
                sum((call.estimated_cost or Decimal(0) for call in priced), Decimal(0))
                if priced and one_currency
                else None
            ),
            currency=next(iter(currencies)) if one_currency else None,
            coverage=_coverage(measured, len(calls)),
            cost_coverage=cost_coverage,
        )


def active_usage_collector() -> UsageCollector | None:
    """Get only this async execution context's explicitly active collector."""
    return _ACTIVE.get()


@contextmanager
def capture_model_usage(previous: ExtractionUsage | None = None) -> Iterator[UsageCollector]:
    """Capture an entire run, including child tasks, and restore nested scopes.

    The caller owns the scope and persists its snapshot. Unrelated concurrent
    requests using the same service/gateway cannot see or mutate this collector.
    """
    collector = UsageCollector(previous)
    token = _ACTIVE.set(collector)
    try:
        yield collector
    finally:
        _ACTIVE.reset(token)
