"""Neutral generation request, including genuine text-only inputs."""

from typing import Literal

from pydantic import Field, JsonValue

from .base import _Contract
from .image_asset import ImageAsset


class ModelRequest(_Contract):
    """Validated completion content and task-specific output specification."""

    prompt: str = Field(min_length=1, repr=False)
    images: tuple[ImageAsset, ...] = ()
    purpose: Literal["ocr", "vision", "fields"] = "fields"
    json_schema: dict[str, JsonValue] | None = None
    max_output_tokens: int = Field(default=4096, ge=1, le=32768)
