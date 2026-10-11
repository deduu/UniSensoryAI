"""
Pipeline orchestration package.

Provides the PipelineExecutor and concrete pipeline stages
that replace the monolithic process_document_job function.
"""

from .context import PipelineContext
from .executor import PipelineExecutor
from .stages import (
    ContentValidationStage,
    ConversionStage,
    EnrichmentStage,
    FormattingStage,
    InferenceStage,
    IngestionStage,
    StructuredOutputStage,
)
from .stages.routing_stage import RoutingStage

# Register all built-in stages
PipelineExecutor.register_stage("ingestion", IngestionStage)
PipelineExecutor.register_stage("conversion", ConversionStage)
PipelineExecutor.register_stage("parsing", ConversionStage)  # Alias for backward compat
PipelineExecutor.register_stage("inference", InferenceStage)
PipelineExecutor.register_stage("structured_output", StructuredOutputStage)
PipelineExecutor.register_stage("content_validation", ContentValidationStage)
PipelineExecutor.register_stage("enrichment", EnrichmentStage)
PipelineExecutor.register_stage("formatting", FormattingStage)
PipelineExecutor.register_stage("routing", RoutingStage)

__all__ = [
    "PipelineContext",
    "PipelineExecutor",
    "IngestionStage",
    "ConversionStage",
    "InferenceStage",
    "ContentValidationStage",
    "StructuredOutputStage",
    "EnrichmentStage",
    "FormattingStage",
    "RoutingStage",
]
