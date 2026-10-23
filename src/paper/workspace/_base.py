"""Strict read-only PAPER workspace navigation contract."""

from pydantic import BaseModel, ConfigDict


class _Summary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
