"""Native PDF table content."""

from pydantic import Field

from .base import _Contract


class TableContent(_Contract):
    """Detected table cells and source location, without invented headers."""

    table_id: str
    page_number: int = Field(ge=1)
    rows: tuple[tuple[str | None, ...], ...]
    bbox: tuple[float, float, float, float] | None = None
