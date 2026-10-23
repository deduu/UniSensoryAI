"""Bounded latest-document search independent of matching policy."""

from typing import Literal

from pydantic import Field

from src.paper.contracts._base import _Contract

from .content import DocumentRole


class DocumentDraftQuery(_Contract):
    """Search filters are applied before pagination within the trusted tenant."""

    q: str = Field(default="", max_length=200)
    role: DocumentRole | None = None
    status: Literal["draft", "reviewed"] | None = None
    limit: int = Field(default=20, ge=1, le=100, strict=True)
    offset: int = Field(default=0, ge=0, strict=True)
