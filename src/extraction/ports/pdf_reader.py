"""Document reader boundary."""

from abc import ABC, abstractmethod

from src.extraction.contracts import DocumentResult, ExtractionOptions, PdfSource


class BasePdfReader(ABC):
    """Async normalization of PDFs without a model dependency."""

    @abstractmethod
    async def read(self, source: PdfSource, options: ExtractionOptions) -> DocumentResult:
        """Read all selected pages and retain source identities."""
        ...
