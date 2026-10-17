"""Stored AP decision with host-derived reviewer and UTC audit time."""

from datetime import datetime, timezone

from pydantic import AwareDatetime, field_validator

from src.paper.contracts._base import Identifier

from .ap_decision import APDecision


class APDecisionRecord(APDecision):
    """Immutable decision provenance recorded by the authorized workflow."""

    decided_by: Identifier
    decided_at: AwareDatetime

    @field_validator("decided_at")
    @classmethod
    def _utc_time(cls, value: datetime) -> datetime:
        return value.astimezone(timezone.utc)
