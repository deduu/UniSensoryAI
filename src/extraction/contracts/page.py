"""Page-level document representation."""

from pydantic import Field

from .base import _Contract
from .image_asset import ImageAsset
from .table import TableContent
from .text_block import TextBlock


class PageContent(_Contract):
    """Ordered PDF content with original page identity."""

    page_number: int = Field(ge=1)
    width: float = Field(gt=0)
    height: float = Field(gt=0)
    text_blocks: tuple[TextBlock, ...] = ()
    images: tuple[ImageAsset, ...] = ()
    tables: tuple[TableContent, ...] = ()
    is_scanned: bool = False
