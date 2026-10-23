"""Conservative exact-ID and normalized-text ranking with explainable signals."""

import re
import unicodedata
from typing import Literal

from src.paper.contracts import AgreementVersion
from src.paper.reconciliation.contracts.rent_invoice_document import RentInvoiceDocument
from src.paper.reconciliation.contracts.review_context import ReconciliationReviewContext

from .candidate import AssociationCandidate
from .matcher import BaseAssociationMatcher
from .period import association_period
from .settings import AssociationSettings
from .signal import AssociationSignal


def _normalized(value: str) -> str:
    return re.sub(r"[^\w]+", " ", unicodedata.normalize("NFKC", value).casefold()).strip()


class DeterministicAssociationMatcher(BaseAssociationMatcher):
    """Provide advisory ranking without inference, money similarity, or ID mapping."""

    def __init__(self, settings: AssociationSettings | None = None) -> None:
        """Inject host-owned deterministic ranking weights."""
        self._settings = AssociationSettings.model_validate(settings or AssociationSettings())

    def evaluate(
        self,
        invoice: RentInvoiceDocument,
        agreement: AgreementVersion,
        *,
        review_context: ReconciliationReviewContext | None = None,
        coverage: Literal["verified", "unverified", "conflicting"] = "unverified",
    ) -> AssociationCandidate:
        """Compare explicit references and retain missing or contradictory values.

        Args:
            invoice: Source values that remain unchanged.
            agreement: Exact immutable reference supplied by the host.
            review_context: Optional independently reviewed billing allocation.
            coverage: Effective-authority validation performed by the service.

        Returns:
            Explainable candidate requiring explicit human confirmation.
        """
        invoice = RentInvoiceDocument.model_validate(invoice)
        agreement = AgreementVersion.model_validate(agreement)
        signals: list[AssociationSignal] = []
        rank = 0
        relevant = False
        comparisons: tuple[tuple[str, str, int, Literal["exact", "supporting"]], ...] = (
            ("contract_number", "Contract reference", self._settings.contract_weight, "exact"),
            ("vendor_id", "Vendor identifier", self._settings.identity_weight, "exact"),
            ("store_id", "Store identifier", self._settings.identity_weight, "exact"),
            ("vendor_name", "Supplier name", self._settings.supplier_weight, "supporting"),
            ("location", "Premises location", self._settings.location_weight, "supporting"),
        )
        for name, label, weight, strength in comparisons:
            actual: str | None = getattr(invoice.fields, name)
            expected: str | None = (
                getattr(agreement.identity, name)
                if strength == "exact"
                else getattr(agreement.draft.terms, name)
            )
            status: Literal["matched", "conflicting", "missing"] = "missing"
            if actual is not None and expected is not None:
                normalized = _normalized(actual)
                same = (
                    actual == expected
                    if strength == "exact"
                    else bool(normalized) and normalized == _normalized(expected)
                )
                status = "matched" if same else "conflicting"
                if same:
                    rank += weight
                    relevant = True
            signals.append(
                AssociationSignal(
                    field=name,
                    label=label,
                    status=status,
                    strength=strength,
                    invoice_value=actual,
                    contract_value=expected,
                    invoice_paths=(f"/{name}",),
                    contract_paths=(f"/{name}",),
                )
            )
        first, last = association_period(invoice, review_context)
        if any(
            boundary is not None
            and not agreement.draft.effective_from <= boundary <= agreement.draft.effective_to
            for boundary in (first, last)
        ):
            coverage = "conflicting"
        elif coverage == "verified" and (first is None or last is None):
            coverage = "unverified"
        allocated = (
            invoice.fields.service_period_start is None
            and invoice.fields.service_period_end is None
            and review_context is not None
        )
        signals.append(
            AssociationSignal(
                field="service_period",
                label=(
                    "Reviewed allocation / approved coverage"
                    if allocated
                    else "Service period / approved coverage"
                ),
                status=(
                    "matched"
                    if coverage == "verified"
                    else "conflicting" if coverage == "conflicting" else "missing"
                ),
                strength="context",
                invoice_value=(
                    f"{first or 'Unknown'} to {last or 'Unknown'}" if first or last else None
                ),
                contract_value=(
                    f"{agreement.draft.effective_from} to {agreement.draft.effective_to}"
                ),
                invoice_paths=() if allocated else ("/service_period_start", "/service_period_end"),
                contract_paths=("/lease_start_date", "/lease_end_date"),
            )
        )
        return AssociationCandidate(
            agreement_id=agreement.agreement_id,
            version_number=agreement.version_number,
            identity=agreement.identity,
            vendor_name=agreement.draft.terms.vendor_name,
            location=agreement.draft.terms.location,
            effective_from=agreement.draft.effective_from,
            effective_to=agreement.draft.effective_to,
            signals=tuple(signals),
            rank=rank,
            relevant=relevant,
            eligible=agreement.approval is not None and coverage != "conflicting",
            coverage=coverage,
        )
