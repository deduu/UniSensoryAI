"""Explicit scope and opt-in mutation for canonical source-index repair."""

from pydantic import Field

from src.paper.contracts._base import Identifier

from ._base import _Summary


class SourceIdentityBackfillQuery(_Summary):
    """Dry-run by default; a batch never reads beyond one hundred tenant-owned jobs."""

    tenant_id: Identifier
    job_id: Identifier | None = None
    limit: int = Field(default=20, ge=1, le=100)
    apply: bool = False
