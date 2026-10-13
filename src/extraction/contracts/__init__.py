"""Serializable contracts for PDF extraction and external schemas."""

from .document import DocumentResult
from .evidence import FieldEvidence
from .external_schema import ExternalSchema
from .field_result import FieldExtractionResult
from .image_asset import ImageAsset
from .issue import ExtractionIssue
from .model_descriptor import ModelDescriptor
from .model_request import ModelRequest
from .model_response import ModelResponse
from .options import ExtractionOptions
from .page import PageContent
from .pdf_source import PdfSource
from .result import ExtractionResult
from .table import TableContent
from .text_block import TextBlock

__all__ = [
    "DocumentResult",
    "ExternalSchema",
    "ExtractionIssue",
    "ExtractionOptions",
    "ExtractionResult",
    "FieldEvidence",
    "FieldExtractionResult",
    "ImageAsset",
    "ModelDescriptor",
    "ModelRequest",
    "ModelResponse",
    "PageContent",
    "PdfSource",
    "TableContent",
    "TextBlock",
]
