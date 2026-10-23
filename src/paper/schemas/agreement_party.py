"""Contractual parties with explicit source role and representation chains."""

from typing import Literal

from pydantic import Field

from src.extraction.contracts.base import _Contract

from ._types import Identity
from .party_representative import PartyRepresentative


class AgreementParty(_Contract):
    """A legal principal rather than a cover-page name or individual signatory."""

    name: Identity | None = Field(
        default=None,
        description="Legal principal established by complete party and representation clauses, not a person merely acting on its behalf; null if unresolved.",
    )
    role: Literal["landlord", "tenant", "other", "unknown"] = Field(
        default="unknown",
        description="Source-established rent supplier/lessor is landlord; occupier/lessee/customer is tenant. Do not infer roles from first/second party order or payment account alone. Use unknown when not established.",
    )
    source_role: Identity | None = Field(
        default=None,
        description="Exact role designation from operative source clauses, e.g. YANG MENYEWAKAN, PENYEWA, LESSOR or LESSEE; preserve the source language. Party order alone is not a role. Null if unknown.",
    )
    representatives: tuple[PartyRepresentative, ...] = Field(
        default=(),
        max_length=32,
        description="ALL source-supported representatives and intermediaries with explicit represents links. Follow all adjacent and continued clauses across pages before assigning a party. If attorney A acts for director B who acts for company C, preserve A->B and B->C separately; do not collapse the chain or omit B. Exclude witnesses and notaries unless they represent this principal. A connected candidate chain still requires human completeness review.",
    )
