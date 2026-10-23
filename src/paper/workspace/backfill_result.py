"""Non-sensitive outcome of an additive canonical source-index repair."""

from pydantic import Field

from ._base import _Summary


class SourceIdentityBackfillResult(_Summary):
    """Only identifiers and counts; no source text, credentials or banking details."""

    dry_run: bool
    scanned: int = Field(ge=0)
    candidates: dict[str, str] = Field(default_factory=dict)
    updated_job_ids: tuple[str, ...] = ()
    skipped_existing_job_ids: tuple[str, ...] = ()
    conflict_job_ids: tuple[str, ...] = ()
    unavailable_job_ids: tuple[str, ...] = ()
