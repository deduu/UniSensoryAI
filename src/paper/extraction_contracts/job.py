"""Lightweight persisted extraction history, with source result loaded on demand."""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from .result import PaperExtractionResult


class PaperExtractionJob(BaseModel):
    """Tenant-scoped job projection used by upload, list, and detail endpoints."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    job_id: str
    filename: str
    schema_name: Literal["rent_agreement", "rent_invoice"]
    content_mode: Literal["text", "multimodal"]
    status: Literal["pending", "processing", "completed", "failed"]
    created_at: datetime
    updated_at: datetime
    model_ids: tuple[Annotated[str, Field(min_length=1)], ...] = ()
    model_usage_recorded: bool = False
    file_size: int | None = Field(default=None, ge=0)
    page_count: int | None = Field(default=None, ge=0)
    warning_count: int = Field(default=0, ge=0)
    extraction_status: Literal["succeeded", "partial"] | None = None
    error: str | None = None
    result: PaperExtractionResult | None = None
