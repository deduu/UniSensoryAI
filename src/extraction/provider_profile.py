"""Validated deployment configuration for model factories."""

from pydantic import Field

from .contracts.base import _Contract


class ProviderProfile(_Contract):
    """Provider configuration resolved by the composition root, never persisted."""

    provider: str = Field(default="openai_compatible", min_length=1)
    model_id: str = Field(min_length=1)
    base_url: str | None = None
    api_key_env: str | None = None
    supports_text: bool = True
    supports_images: bool = False
    supports_native_json: bool = False
    max_input_chars: int = Field(default=48000, ge=1024)
    max_images: int = Field(default=1, ge=0)
    concurrency: int = Field(default=1, ge=1)
