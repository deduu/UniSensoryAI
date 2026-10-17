"""Source-qualified supporting attachment for a rent invoice package."""

from src.paper.schemas import SupportingDocumentSchema

from ._base import _Document


class SupportingDocument(_Document):
    """A supporting attachment with a host-configurable source document type."""

    fields: SupportingDocumentSchema
