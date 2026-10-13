"""Self-contained image assets avoid dangling temporary paths."""

from typing import Literal

from pydantic import Field

from .base import _Contract


class ImageAsset(_Contract):
    """PNG image or page raster with source coordinates in PDF points."""

    asset_id: str
    page_number: int = Field(ge=1)
    data_base64: str = Field(repr=False)
    media_type: Literal["image/png", "image/jpeg"] = "image/png"
    bbox: tuple[float, float, float, float] | None = None
    kind: Literal["image", "page"] = "image"
    description: str | None = None
