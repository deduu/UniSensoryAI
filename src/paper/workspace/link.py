"""Strict read-only PAPER workspace navigation contract."""

from typing import Literal

from pydantic import Field

from src.paper.contracts._base import Identifier

from ._base import _Summary


class WorkspaceLink(_Summary):
    """Exact saved revision referring to a source; historical links remain explicit."""

    kind: Literal["agreement", "case"]
    id: Identifier
    version_number: int = Field(ge=1)
    status: str
    is_latest: bool
    label: str | None = None
