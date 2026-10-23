"""One approved contract suggestion and its explicit comparison signals."""

from datetime import date
from typing import Literal

from pydantic import Field, PositiveInt

from src.paper.contracts import AgreementIdentity
from src.paper.contracts._base import Identifier, _Contract

from .signal import AssociationSignal


class AssociationCandidate(_Contract):
    """Advisory ranking; eligible candidates still require reviewer confirmation."""

    agreement_id: Identifier
    version_number: PositiveInt
    identity: AgreementIdentity
    vendor_name: str | None = None
    location: str | None = None
    effective_from: date
    effective_to: date
    signals: tuple[AssociationSignal, ...] = Field(default=(), max_length=64)
    rank: int = Field(ge=0)
    relevant: bool
    eligible: bool
    coverage: Literal["verified", "unverified", "conflicting"]
