"""Paginated exact source-draft snapshots with truthful total count."""

from pydantic import Field

from src.paper.contracts._base import _Contract

from .version import DocumentDraftVersion


class DocumentDraftPage(_Contract):
    """A bounded page of latest drafts or retained history."""

    items: tuple[DocumentDraftVersion, ...]
    total: int = Field(ge=0)
    limit: int = Field(ge=1, le=100)
    offset: int = Field(ge=0)
