"""Located document text."""

from typing import Literal

from pydantic import Field

from .base import _Contract


class TextBlock(_Contract):
    """Text with stable identity and PDF-point source coordinates."""

    block_id: str
    page_number: int = Field(ge=1)
    text: str
    bbox: tuple[float, float, float, float] | None = None
    origin: Literal["native", "ocr", "vision"] = "native"
