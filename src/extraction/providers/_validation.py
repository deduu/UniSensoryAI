"""Shared provider boundary validation without importing model SDKs."""

from typing import Any

from src.extraction.contracts import ModelDescriptor, ModelRequest, ModelResponse
from src.extraction.errors import ExtractionError
from src.extraction.usage import normalized_usage


def validate_request(descriptor: ModelDescriptor, request: ModelRequest) -> None:
    """Check provider compatibility before loading or calling a model."""
    if len(request.prompt) > descriptor.max_input_chars:
        raise ExtractionError("context_limit", "The model input exceeds its configured limit.")
    if request.images:
        if not descriptor.supports_images or len(request.images) > descriptor.max_images:
            raise ExtractionError(
                "unsupported_model_features", "The model does not support these image inputs."
            )
    elif not descriptor.supports_text:
        raise ExtractionError(
            "unsupported_model_features", "The model does not support text-only inputs."
        )


def normalize_response(
    content: Any,
    model_id: str,
    finish_reason: Any = None,
    usage: Any = None,
    *,
    response_model_id: str | None = None,
) -> ModelResponse:
    """Reject incomplete output and retain only safe normalized metadata."""
    counters = normalized_usage(usage)
    if (
        not isinstance(content, str)
        or not content.strip()
        or (finish_reason is not None and not isinstance(finish_reason, str))
        or finish_reason in {"length", "max_tokens", "content_filter", "error", "cancelled"}
    ):
        raise ExtractionError(
            "model_response_invalid",
            "The model returned an empty, invalid, or incomplete response.",
            usage=counters,
            response_model_id=response_model_id,
        )
    return ModelResponse(
        content=content,
        model_id=model_id,
        finish_reason=finish_reason,
        usage=counters,
        response_model_id=response_model_id,
    )
