"""Registry: document_subtype → Pydantic schema class."""

from __future__ import annotations

import logging
from typing import Optional, Type

from pydantic import BaseModel

from .schemas import (
    FormSchema,
    GenericReportSchema,
    InvoiceSchema,
    ReceiptSchema,
)

logger = logging.getLogger(__name__)

# Mapping of document_subtype (as written to PipelineContext) → schema class.
# Subtypes not in this map fall back to GenericReportSchema.
_DEFAULT_SCHEMAS: dict[str, Type[BaseModel]] = {
    "invoice": InvoiceSchema,
    "receipt": ReceiptSchema,
    "form": FormSchema,
    "report": GenericReportSchema,
}


class SchemaRegistry:
    """Resolve a Pydantic schema for a document subtype.

    The registry is intentionally a thin dict; callers pass a subtype string
    and receive a schema class (or ``None`` if extraction should be skipped
    for that subtype).
    """

    def __init__(
        self,
        schemas: Optional[dict[str, Type[BaseModel]]] = None,
        default: Optional[Type[BaseModel]] = GenericReportSchema,
    ) -> None:
        self._schemas = dict(_DEFAULT_SCHEMAS if schemas is None else schemas)
        self._default = default

    def get(self, document_subtype: Optional[str]) -> Optional[Type[BaseModel]]:
        """Return the schema for ``document_subtype``.

        Args:
            document_subtype: Subtype string as set by the ingestion stage.

        Returns:
            The matching schema class. When the subtype is unknown, returns
            the registry default (``GenericReportSchema`` by default).
            Returns ``None`` only if the registry was constructed with
            ``default=None`` and the subtype is unknown.
        """
        if document_subtype and document_subtype in self._schemas:
            return self._schemas[document_subtype]
        return self._default

    def register(
        self, document_subtype: str, schema_cls: Type[BaseModel]
    ) -> None:
        """Register a new (subtype, schema) pair."""
        self._schemas[document_subtype] = schema_cls

    @property
    def known_subtypes(self) -> list[str]:
        return list(self._schemas.keys())


_registry: Optional[SchemaRegistry] = None


def get_schema_registry() -> SchemaRegistry:
    """Return the module-level singleton registry."""
    global _registry
    if _registry is None:
        _registry = SchemaRegistry()
    return _registry


def reset_schema_registry() -> None:
    """Reset the singleton — test-only seam."""
    global _registry
    _registry = None
