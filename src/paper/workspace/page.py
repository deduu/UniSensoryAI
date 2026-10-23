"""Strict read-only PAPER workspace navigation contract."""

from typing import Generic, TypeVar

from pydantic import Field

from ._base import _Summary

_Item = TypeVar("_Item")


class WorkspacePage(_Summary, Generic[_Item]):
    """Total matches and one deterministically ordered page."""

    items: tuple[_Item, ...]
    total: int = Field(ge=0)
    limit: int = Field(ge=1, le=100)
    offset: int = Field(ge=0)
