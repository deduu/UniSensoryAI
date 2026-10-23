"""Strict read-only PAPER workspace navigation contract."""

from datetime import datetime
from typing import Literal

from pydantic import Field

from src.paper.contracts._base import Identifier

from ._base import _Summary


class WorkspaceAssociation(_Summary):
    """A navigation relationship, never a declaration of assessed billing authority."""

    agreement_id: Identifier
    version_number: int | None = Field(default=None, ge=1)
    kind: Literal["confirmed", "legacy_identity"]
    confirmed_by: str | None = None
    confirmed_at: datetime | None = None
