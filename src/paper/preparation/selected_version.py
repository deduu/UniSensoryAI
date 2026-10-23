"""Server-resolved source review provenance retained in a case snapshot."""

from typing import Literal

from pydantic import AwareDatetime, PositiveInt

from src.paper.contracts._base import Identifier, _Contract


class SelectedDocumentVersion(_Contract):
    """Record exactly which reviewed document version a case consumed."""

    draft_id: Identifier
    version_number: PositiveInt
    role: Literal["rent_invoice", "tax_invoice", "utility_statement", "supporting_document"]
    source_document_id: Identifier
    reviewed_by: Identifier
    reviewed_at: AwareDatetime
