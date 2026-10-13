"""Safe diagnostics without document values or provider exception strings."""

from .base import _Contract


class ExtractionIssue(_Contract):
    """A machine-readable extraction warning."""

    code: str
    message: str
    page_number: int | None = None
    field_path: str | None = None
