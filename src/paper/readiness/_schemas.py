"""Bounded field catalog shared by requirement validation and evaluation."""

from decimal import Decimal
from typing import Literal, get_args

from pydantic import BaseModel, TypeAdapter

from src.paper.schemas import (
    RentInvoiceSchema,
    SupportingDocumentSchema,
    TaxInvoiceSchema,
    UtilityStatementSchema,
)
from src.paper.schemas._types import DecimalString

DocumentRole = Literal["rent_invoice", "tax_invoice", "utility_statement", "supporting_document"]
SCHEMAS: dict[str, type[BaseModel]] = {
    "rent_invoice": RentInvoiceSchema,
    "tax_invoice": TaxInvoiceSchema,
    "utility_statement": UtilityStatementSchema,
    "supporting_document": SupportingDocumentSchema,
}


def scalar_fields(role: str) -> tuple[str, ...]:
    """Return supported scalar source fields, excluding arbitrary extension objects."""
    return tuple(name for name in SCHEMAS[role].model_fields if name != "extensions")


def validate_scalar(role: str, field: str, value: object) -> str | int | float | bool:
    """Validate an equality value using the same bounded scalar field as extraction."""
    if field not in scalar_fields(role):
        raise ValueError("Field conditions reference an unsupported scalar field.")
    definition = SCHEMAS[role].model_fields[field]
    adapter: TypeAdapter[object] = TypeAdapter(definition.rebuild_annotation())
    validated: object = adapter.dump_python(adapter.validate_python(value), mode="json")
    if validated is None or not isinstance(validated, (str, int, float, bool)):
        raise ValueError("Equality requires a supported non-null scalar value.")
    return validated


def scalar_equals(role: str, field: str, first: object, second: object) -> bool:
    """Compare typed JSON values, using exact decimal semantics for schema amounts."""
    definition = SCHEMAS[role].model_fields[field]
    decimal_field = definition.annotation == DecimalString or DecimalString in get_args(
        definition.annotation
    )
    if decimal_field and isinstance(first, str) and isinstance(second, str):
        return Decimal(first) == Decimal(second)
    return type(first) is type(second) and first == second
