"""A bounded suggestion batch whose completeness remains explicit."""

from typing import Literal

from pydantic import Field

from src.paper.contracts._base import Identifier, _Contract

from .candidate import AssociationCandidate


class AssociationCandidates(_Contract):
    """Manual alternatives remain visible even when no positive signal exists."""

    candidates: tuple[AssociationCandidate, ...] = Field(default=(), max_length=100)
    state: Literal["suggestions", "no_match", "ambiguous"]
    offset: int = Field(ge=0)
    limit: int = Field(ge=1, le=100)
    next_offset: int | None = Field(default=None, ge=0)
    has_more: bool
    exhaustive: bool
    history_incomplete: bool = False
    requires_confirmation: Literal[True] = True
    policy_id: Identifier
    policy_version: Identifier
