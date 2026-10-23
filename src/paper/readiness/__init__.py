"""Portable host requirements and pure document-selection readiness contracts."""

from typing import TYPE_CHECKING

from .check import ReadinessCheck
from .condition import FieldCondition
from .requirement import FieldRequirement
from .result import ReadinessResult

if TYPE_CHECKING:
    from src.paper.reconciliation.contracts import InvoicePackage, ReconciliationAssessment
    from src.paper.reconciliation.settings import ReconciliationSettings

__all__ = ["FieldCondition", "FieldRequirement", "ReadinessCheck", "ReadinessResult", "evaluate"]


def evaluate(
    package: "InvoicePackage",
    assessment: "ReconciliationAssessment",
    settings: "ReconciliationSettings",
) -> ReadinessResult:
    """Evaluate selected documents without persistence, inference, or external I/O."""
    # Settings import requirement contracts; defer the evaluation dependency so
    # importing those contracts never imports the reconciliation engine recursively.
    from .evaluation import evaluate as evaluate_readiness

    return evaluate_readiness(package, assessment, settings)
