"""Deterministic content binding without model or repository dependencies."""

import hashlib
import json

from pydantic import BaseModel

from .contracts import InvoicePackage, ReconciliationAssessment
from .settings import ReconciliationSettings


def _fingerprint(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _model_fingerprint(model: BaseModel) -> str:
    return _fingerprint(model.model_dump(mode="json", round_trip=True))


def package_fingerprint(package: InvoicePackage) -> str:
    """Bind fields, source identifiers, diagnostics, and evidence in a package."""
    return _model_fingerprint(InvoicePackage.model_validate(package))


def policy_fingerprint(
    settings: ReconciliationSettings, rule_versions: tuple[tuple[str, str], ...] = ()
) -> str:
    """Bind host settings and explicitly versioned injected rule implementations."""
    settings = ReconciliationSettings.model_validate(settings)
    if not rule_versions:
        return _model_fingerprint(settings)
    return _fingerprint({"settings": settings.model_dump(mode="json"), "rules": rule_versions})


def assessment_fingerprint(assessment: ReconciliationAssessment) -> str:
    """Bind persisted findings and authority references for stale-result checks."""
    return _model_fingerprint(ReconciliationAssessment.model_validate(assessment))


def duplicate_key(package: InvoicePackage) -> str | None:
    """Hash canonical vendor plus nonempty invoice number for tenant-scoped claims.

    Tenant qualification belongs to the repository. Invoice numbers are compared
    exactly after schema whitespace normalization, without speculative case-folding.
    """
    package = InvoicePackage.model_validate(package)
    number = package.invoice.fields.invoice_number
    if number is None:
        return None
    return _fingerprint({"vendor_id": package.identity.vendor_id, "invoice_number": number})


def installment_duplicate_key(package: InvoicePackage) -> str | None:
    """Identify one rent obligation independently of invoice or agreement revisions.

    Args:
        package: Validated package with an explicit stable installment identifier.

    Returns:
        A domain-separated SHA-256 key, or None for ordinary invoices. The
        repository qualifies it by tenant and reserves it only for an eligible
        assessment. Schedule/version names are excluded so amendments cannot
        reopen a previously claimed obligation merely by changing those names.
    """
    package = InvoicePackage.model_validate(package)
    installment_id = package.invoice.fields.installment_id
    if installment_id is None:
        return None
    return _fingerprint(
        {
            "claim_type": "paper.installment.v1",
            "identity": package.identity.model_dump(mode="json"),
            "installment_id": installment_id,
        }
    )
