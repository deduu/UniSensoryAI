"""Trusted review provenance retained with the associated invoice case."""

from typing import Annotated

from pydantic import AwareDatetime, Field, StringConstraints

from src.paper.contracts._base import Identifier

from .selection import AssociationSelection
from .signal import AssociationSignal


class AssociationConfirmation(AssociationSelection):
    """Server-stamped decision binding a source invoice and review allocation."""

    confirmed_by: Identifier
    confirmed_at: AwareDatetime
    invoice_fingerprint: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
    signals: tuple[AssociationSignal, ...] = Field(default=(), max_length=64)
    policy_id: Identifier
    policy_version: Identifier
