"""Qualify page-local extraction evidence with its source document."""

from src.extraction.contracts import FieldEvidence

from ._base import Identifier, _Contract


class AgreementEvidence(_Contract):
    """Source reference retained alongside agreement terms."""

    document_id: Identifier
    evidence: FieldEvidence
