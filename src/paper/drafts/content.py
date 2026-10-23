"""Role-qualified external document data without reconciliation requirements."""

from typing import Literal

from pydantic import model_validator

from src.paper.contracts._base import _Contract
from src.paper.reconciliation.contracts import (
    RentInvoiceDocument,
    SupportingDocument,
    TaxInvoiceDocument,
    UtilityStatementDocument,
)

DocumentRole = Literal["rent_invoice", "tax_invoice", "utility_statement", "supporting_document"]
DraftDocument = (
    RentInvoiceDocument | TaxInvoiceDocument | UtilityStatementDocument | SupportingDocument
)
_DOCUMENT_TYPES: dict[str, type[_Contract]] = {
    "rent_invoice": RentInvoiceDocument,
    "tax_invoice": TaxInvoiceDocument,
    "utility_statement": UtilityStatementDocument,
    "supporting_document": SupportingDocument,
}


class DocumentDraftContent(_Contract):
    """A source-qualified document; missing business values may remain null."""

    role: DocumentRole
    document: DraftDocument

    @model_validator(mode="before")
    @classmethod
    def _role_document(cls, value: object) -> object:
        if isinstance(value, dict):
            role = value.get("role")
            document = value.get("document")
            model = _DOCUMENT_TYPES.get(role) if isinstance(role, str) else None
            if model is not None and document is not None:
                if isinstance(document, _Contract):
                    document = document.model_dump(mode="json")
                return {**value, "document": model.model_validate(document)}
        return value
