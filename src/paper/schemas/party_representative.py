"""Source-derived signatory capacity, distinct from the contractual principal."""

from pydantic import Field

from src.extraction.contracts.base import _Contract

from ._types import Identity


class PartyRepresentative(_Contract):
    """A person acting for a party; representation never transfers party identity."""

    name: Identity = Field(description="Source-stated representative or signatory name.")
    represents: Identity | None = Field(
        default=None,
        description="Exact person or legal entity represented at THIS source-stated step of the acting-for/on-behalf-of chain; null if unclear. Preserve every intermediary: if attorney A acts for director B who acts for company C, record A represents B AND B represents C. Never collapse A directly to C or omit B. A representative is not automatically the landlord or tenant.",
    )
    capacity: Identity | None = Field(
        default=None,
        description="Source-stated capacity, such as director or attorney, preserving the source language; null if unknown. Do not guess a capacity from a name or infer omitted authority.",
    )
