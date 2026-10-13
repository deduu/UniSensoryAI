"""Validated PDF input for in-process hosts."""

from pathlib import Path

from pydantic import Field, model_validator

from .base import _Contract


class PdfSource(_Contract):
    """A local PDF path or an in-memory PDF, never both."""

    path: Path | None = None
    data: bytes | None = Field(default=None, repr=False)
    filename: str = Field(default="document.pdf", min_length=1, max_length=255)

    @model_validator(mode="after")
    def validate_source(self) -> "PdfSource":
        """Require one input and a PDF extension for filesystem inputs."""
        if (self.path is None) == (self.data is None):
            raise ValueError("Provide exactly one of path or data.")
        if self.path is not None and self.path.suffix.lower() != ".pdf":
            raise ValueError("Only PDF sources are supported.")
        return self
