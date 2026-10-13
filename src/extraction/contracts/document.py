"""Reusable document output."""

from typing import Literal

from pydantic import computed_field

from .base import _Contract
from .issue import ExtractionIssue
from .page import PageContent


class DocumentResult(_Contract):
    """Full selected document content and evidence, independent of business schema."""

    document_id: str
    source_name: str
    content_mode: Literal["text", "multimodal"]
    text: str
    pages: tuple[PageContent, ...]
    warnings: tuple[ExtractionIssue, ...] = ()

    @computed_field  # type: ignore[prop-decorator]
    @property
    def page_count(self) -> int:
        """Return the number of selected pages, including blank pages."""
        return len(self.pages)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def status(self) -> Literal["succeeded", "partial"]:
        """Report incomplete extraction explicitly."""
        return "partial" if self.warnings else "succeeded"
