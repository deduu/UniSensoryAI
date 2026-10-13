"""Output representation and text acquisition are independent settings."""

from typing import Literal

from pydantic import Field, model_validator

from .base import _Contract


class ExtractionOptions(_Contract):
    """Validated page selection, representation, and resource budgets."""

    content_mode: Literal["text", "multimodal"] = "text"
    text_strategy: Literal["native_only", "native_then_ocr"] = "native_then_ocr"
    start_page: int | None = Field(default=None, ge=1)
    end_page: int | None = Field(default=None, ge=1)
    vision_profile: str = Field(default="vision", min_length=1)
    fields_profile: str = Field(default="fields", min_length=1)
    max_bytes: int = Field(default=100 * 1024 * 1024, ge=1)
    max_pages: int = Field(default=500, ge=1)
    max_asset_bytes: int = Field(default=64 * 1024 * 1024, ge=1)
    render_dpi: int = Field(default=144, ge=72, le=300)
    timeout_seconds: float = Field(default=300.0, gt=0, le=3600)

    @model_validator(mode="after")
    def validate_selection(self) -> "ExtractionOptions":
        """Reject reversed page selections."""
        if self.start_page and self.end_page and self.start_page > self.end_page:
            raise ValueError("start_page cannot exceed end_page.")
        return self
