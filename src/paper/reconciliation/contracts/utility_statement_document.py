"""Utility statement fields qualified by their source document."""

from src.paper.schemas import UtilityStatementSchema

from ._base import _Document


class UtilityStatementDocument(_Document):
    """A utility statement's source-derived fields and extraction diagnostics."""

    fields: UtilityStatementSchema
