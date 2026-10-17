"""Validated deployment-independent PAPER extraction job inputs."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class PaperExtractionParameters(BaseModel):
    """Small persisted job settings; credentials and document contents are excluded."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    workflow: Literal["paper_extraction"] = "paper_extraction"
    schema_name: Literal["rent_agreement", "rent_invoice"]
    content_mode: Literal["text", "multimodal"] = "text"
    original_filename: str = Field(min_length=1, max_length=255)
    file_size: int = Field(ge=1, le=100 * 1024 * 1024)
    retry_of: str | None = Field(default=None, min_length=1, max_length=50)
