"""Explicit tenant-scoped archive or restore intent for retained extraction attempts."""

from typing import Annotated

from pydantic import Field, StrictBool, StringConstraints, model_validator

from src.extraction.contracts.base import _Contract

_JobIdentifier = Annotated[
    str, StringConstraints(strict=True, min_length=1, max_length=50, pattern=r"^[A-Za-z0-9-]+$")
]


class ExtractionArchiveRequest(_Contract):
    """Change active-list visibility while retaining source files and audit history."""

    job_ids: tuple[_JobIdentifier, ...] = Field(min_length=1, max_length=100)
    archived: StrictBool

    @model_validator(mode="after")
    def unique_jobs(self) -> "ExtractionArchiveRequest":
        """Reject duplicate targets rather than disguising an ambiguous batch."""
        if len(set(self.job_ids)) != len(self.job_ids):
            raise ValueError("Extraction archive targets must be unique.")
        return self
