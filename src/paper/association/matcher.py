"""Replaceable pure association ranking boundary without repository or model I/O."""

from abc import ABC, abstractmethod
from typing import Literal

from src.paper.contracts import AgreementVersion
from src.paper.reconciliation.contracts.rent_invoice_document import RentInvoiceDocument
from src.paper.reconciliation.contracts.review_context import ReconciliationReviewContext

from .candidate import AssociationCandidate


class BaseAssociationMatcher(ABC):
    """Rank a supplied immutable contract without assigning invoice source values."""

    @abstractmethod
    def evaluate(
        self,
        invoice: RentInvoiceDocument,
        agreement: AgreementVersion,
        *,
        review_context: ReconciliationReviewContext | None = None,
        coverage: Literal["verified", "unverified", "conflicting"] = "unverified",
    ) -> AssociationCandidate:
        """Return explicit supporting/conflicting signals for human confirmation."""
        raise NotImplementedError
