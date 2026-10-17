"""Persisted publication audit."""

from pydantic import AwareDatetime

from ._base import Identifier
from .approval_decision import ApprovalDecision


class ApprovalRecord(ApprovalDecision):
    """Immutable approval attached to one exact agreement version."""

    approved_by: Identifier
    approved_at: AwareDatetime
