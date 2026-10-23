"""Safe failures for recoverable extraction-list cleanup."""

from typing import Literal


class PaperExtractionArchiveError(Exception):
    """Reject an archive batch without exposing identifiers or source values."""

    def __init__(self, code: Literal["not_found", "active_extraction"], message: str) -> None:
        """Initialize an atomic archive failure.

        Args:
            code: Transport-independent missing-scope or active-worker conflict.
            message: Safe explanation without private document or tenant values.
        """
        super().__init__(message)
        self.code = code
