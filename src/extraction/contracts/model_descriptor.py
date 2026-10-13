"""Provider features and resource limits."""

from pydantic import Field

from .base import _Contract


class ModelDescriptor(_Contract):
    """Capabilities of one configured generation model."""

    model_id: str = Field(min_length=1)
    supports_text: bool = True
    supports_images: bool = False
    supports_native_json: bool = False
    max_input_chars: int = Field(default=48000, ge=1024)
    max_images: int = Field(default=1, ge=0)
    concurrency: int = Field(default=1, ge=1)
