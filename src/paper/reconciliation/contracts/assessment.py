"""Persistable result bound to the exact package and host policy."""

from typing import Literal

from pydantic import Field

from src.paper.contracts._base import Identifier, _Contract

from ._base import Sha256
from .agreement_reference import AgreementReference
from .finding import ReconciliationFinding


class ReconciliationAssessment(_Contract):
    """An assessment is advisory; a separate authorized AP decision owns approval."""

    outcome: Literal["matched", "incomplete", "mismatched", "needs_review"]
    findings: tuple[ReconciliationFinding, ...] = Field(default=(), max_length=10000)
    agreement_reference: AgreementReference | None = None
    policy_id: Identifier
    policy_version: Identifier
    policy_fingerprint: Sha256
    package_fingerprint: Sha256
