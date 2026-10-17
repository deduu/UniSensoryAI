"""Explicit AP reviewer decision; authority is supplied by the host separately."""

from typing import Literal

from pydantic import Field, model_validator

from src.paper.contracts._base import Identifier, Reason, _Contract


class APDecision(_Contract):
    """An approval or rejection with reason and precisely accepted finding codes."""

    action: Literal["approve", "reject"]
    reason: Reason
    override_codes: tuple[Identifier, ...] = Field(default=(), max_length=64)

    @model_validator(mode="after")
    def _unique_codes(self) -> "APDecision":
        if len(set(self.override_codes)) != len(self.override_codes):
            raise ValueError("Decision override codes must be unique.")
        return self
