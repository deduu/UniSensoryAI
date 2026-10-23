"""Injectable party-role validation independent of models, transport and storage."""

from abc import ABC, abstractmethod
from collections.abc import Sequence

from src.extraction.contracts import DocumentResult, ExtractionIssue, FieldEvidence
from src.paper.schemas.rent_agreement import RentAgreementSchema


class BasePartyRoleValidator(ABC):
    """Validate source-derived principals without modifying or approving them."""

    @abstractmethod
    def validate(
        self,
        terms: RentAgreementSchema,
        evidence: Sequence[FieldEvidence],
        *,
        document: DocumentResult | None = None,
    ) -> tuple[ExtractionIssue, ...]:
        """Return safe role diagnostics while retaining explicit human review.

        Args:
            terms: Validated extraction candidates, never rewritten by validation.
            evidence: Field references scoped to the document by the caller.
            document: Optional original extracted blocks for literal verification.

        Returns:
            Review-required and unresolved role/evidence diagnostics.
        """
        ...
