"""Pipeline context — typed data carrier between pipeline stages."""

from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class PipelineContext(BaseModel):
    """Typed context that flows through pipeline stages.

    Each stage reads what it needs, performs work, and writes results
    back to the context. This ensures stages remain decoupled while
    sharing a consistent data contract.

    Attributes:
        job_id: Unique identifier for the processing job.
        file_path: Absolute path to the uploaded document.
        model_id: Model identifier for VLM inference.
        api_keys: Optional API key overrides for cloud models.
        start_page: Optional 1-indexed start page (inclusive).
        end_page: Optional 1-indexed end page (inclusive).
        document_type: Detected document type string (set by ingestion stage).
        content_items: Converted content items — images or text (set by conversion stage).
        model_instance: Loaded model reference (set by inference stage).
        raw_results: Per-item inference results (set by inference stage).
        formatted_output: Final aggregated output dict (set by formatting stage).
        errors: Accumulated errors from any stage.
        stage_timings: Stage name → duration in seconds.
    """

    job_id: str = ""
    file_path: Path
    model_id: str = "qwen2-vl-2b-instruct"
    api_keys: Optional[Dict[str, str]] = None
    start_page: Optional[int] = None
    end_page: Optional[int] = None

    # Populated by stages — using Any to avoid coupling to PIL/model types
    document_type: Optional[str] = None
    content_items: Optional[List[Any]] = None
    model_instance: Any = None
    raw_results: Optional[List[str]] = None
    formatted_output: Optional[Dict[str, Any]] = None

    errors: List[str] = Field(default_factory=list)
    stage_timings: Dict[str, float] = Field(default_factory=dict)

    model_config = {"arbitrary_types_allowed": True}
