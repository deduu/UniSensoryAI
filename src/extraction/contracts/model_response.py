"""Normalized completion output."""

from pydantic import Field

from .base import _Contract


class ModelResponse(_Contract):
    """Content and resolved model identity; provider errors must raise."""

    content: str = Field(min_length=1, repr=False)
    model_id: str
    finish_reason: str | None = None
    usage: dict[str, int] = Field(default_factory=dict)
    response_model_id: str | None = None
