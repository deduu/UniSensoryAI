"""Shared pure requirement resolution for readiness and actual reconciliation."""

from typing import TYPE_CHECKING

from src.paper.reconciliation.contracts import (
    InvoicePackage,
    RentInvoiceDocument,
    SupportingDocument,
    TaxInvoiceDocument,
    UtilityStatementDocument,
)

from ._schemas import DocumentRole, scalar_equals, scalar_fields
from .requirement import FieldRequirement

if TYPE_CHECKING:
    from src.paper.reconciliation.settings import ReconciliationSettings

SelectedDocument = (
    RentInvoiceDocument | TaxInvoiceDocument | UtilityStatementDocument | SupportingDocument
)


def documents_by_role(package: InvoicePackage) -> dict[DocumentRole, tuple[SelectedDocument, ...]]:
    """Return the selected bounded documents by their explicit canonical role."""
    return {
        "rent_invoice": (package.invoice,),
        "tax_invoice": package.tax_invoices,
        "utility_statement": package.utility_statements,
        "supporting_document": package.supporting_documents,
    }


def has_value(value: object) -> bool:
    """Keep zero and false distinct from absent or empty source values."""
    return value is not None and value != "" and value != () and value != {}


def effective_requirements(
    settings: "ReconciliationSettings", role: DocumentRole
) -> tuple[FieldRequirement, ...]:
    """Overlay explicit policy on legacy defaults and enumerate optional schema fields."""
    required = (
        settings.required_invoice_fields
        if role == "rent_invoice"
        else settings.required_tax_fields if role == "tax_invoice" else ()
    )
    overrides = {item.field: item for item in settings.field_requirements if item.role == role}
    names = dict.fromkeys(
        (
            *(name for name in required if name in scalar_fields(role)),
            *overrides,
            *scalar_fields(role),
        )
    )
    return tuple(
        overrides.get(name)
        or FieldRequirement(
            role=role,
            field=name,
            requirement="required" if name in required else "optional",
            reason=(
                "Required by the host reconciliation policy."
                if name in required
                else "Optional source field under the current host policy."
            ),
        )
        for name in names
    )


def requirement_active(
    requirement: FieldRequirement,
    package: InvoicePackage,
    document: SelectedDocument | None = None,
) -> bool:
    """Resolve a bounded predicate; same-role conditions apply per document."""
    if requirement.requirement != "conditional":
        return requirement.requirement == "required"
    condition = requirement.when
    assert condition is not None
    documents = (
        (document,)
        if document is not None and condition.role == requirement.role
        else documents_by_role(package)[condition.role]
    )
    values = [item.fields.model_dump(mode="json").get(condition.field) for item in documents]
    if condition.operator == "present":
        return any(has_value(value) for value in values)
    if condition.operator == "absent":
        return not any(has_value(value) for value in values)
    return any(
        scalar_equals(condition.role, condition.field, value, condition.value) for value in values
    )


def required_field_names(
    settings: "ReconciliationSettings",
    role: DocumentRole,
    package: InvoicePackage,
    document: SelectedDocument | None = None,
) -> tuple[str, ...]:
    """Preserve legacy ordering and apply only explicitly configured presence changes."""
    legacy = (
        settings.required_invoice_fields
        if role == "rent_invoice"
        else settings.required_tax_fields if role == "tax_invoice" else ()
    )
    overrides = {item.field: item for item in settings.field_requirements if item.role == role}
    return tuple(
        name
        for name in dict.fromkeys((*legacy, *overrides))
        if name not in overrides or requirement_active(overrides[name], package, document)
    )
