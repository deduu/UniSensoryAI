"""Model-independent boundary for original PDF page previews."""

from abc import ABC, abstractmethod
from pathlib import Path


class BasePdfPagePreview(ABC):
    """Render source pages without extracting or interpreting their contents."""

    @abstractmethod
    async def render(self, path: Path, page_number: int) -> bytes:
        """Return a bounded PNG of a one-based original document page.

        Args:
            path: Authorized source path resolved by the host storage layer.
            page_number: One-based page number in the original PDF.

        Returns:
            PNG image bytes preserving the original page appearance.
        """
        ...
