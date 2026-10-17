"""Historical invoice package, assessment, and optional authorized decision."""

from typing import Literal

from pydantic import AwareDatetime, PositiveInt, computed_field

from src.paper.contracts._base import Identifier, _Contract

from .ap_decision_record import APDecisionRecord
from .assessment import ReconciliationAssessment
from .package import InvoicePackage


class InvoiceCaseVersion(_Contract):
    """A correction creates a new version rather than rewriting case history."""

    case_id: Identifier
    tenant_id: Identifier
    version_number: PositiveInt
    package: InvoicePackage
    assessment: ReconciliationAssessment
    created_by: Identifier
    created_at: AwareDatetime
    duplicate_of: Identifier | None = None
    decision: APDecisionRecord | None = None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def status(
        self,
    ) -> Literal[
        "approved", "rejected", "duplicate", "matched", "incomplete", "mismatched", "needs_review"
    ]:
        """Only a recorded reviewer decision makes the case approved or rejected."""
        if self.decision is not None:
            return "approved" if self.decision.action == "approve" else "rejected"
        return "duplicate" if self.duplicate_of is not None else self.assessment.outcome
