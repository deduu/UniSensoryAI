"""Port for source-derived party enrichment, separate from approval and storage."""

from abc import ABC, abstractmethod

from src.extraction.contracts import DocumentResult, ExtractionOptions, FieldExtractionResult


class BaseAgreementPartyExtractor(ABC):
    """Enrich new agreement candidates without mutating earlier extraction records."""

    @abstractmethod
    async def enrich(
        self,
        document: DocumentResult,
        fields: FieldExtractionResult,
        options: ExtractionOptions,
    ) -> FieldExtractionResult:
        """Return a new role-aware candidate retaining other terms and diagnostics.

        Args:
            document: Complete source content and qualified block identifiers.
            fields: Initial agreement extraction to preserve outside the party scope.
            options: Host-owned profile and resource limits.

        Returns:
            Candidate fields with explicit role validation and review diagnostics.
        """
        ...
