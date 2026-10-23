"""Explain one contract-association comparison without inventing source evidence."""

from typing import Literal

from pydantic import Field

from src.paper.contracts._base import Identifier, _Contract


class AssociationSignal(_Contract):
    """Source values and exact field paths supporting or contradicting a candidate."""

    field: Identifier
    label: str = Field(min_length=1, max_length=256)
    status: Literal["matched", "conflicting", "missing"]
    strength: Literal["exact", "supporting", "context"]
    invoice_value: str | None = Field(default=None, max_length=20000)
    contract_value: str | None = Field(default=None, max_length=20000)
    invoice_paths: tuple[str, ...] = Field(default=(), max_length=16)
    contract_paths: tuple[str, ...] = Field(default=(), max_length=16)
