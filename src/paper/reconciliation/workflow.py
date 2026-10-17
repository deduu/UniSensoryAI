"""Durable PAPER invoice assessment and explicit, version-bound AP review."""

import asyncio
from collections.abc import Awaitable
from typing import TypeVar

import structlog
from pydantic import Field

from src.paper.contracts import AgreementActor, AgreementLookup, AgreementVersion
from src.paper.contracts._base import Identifier, _Contract
from src.paper.errors import AgreementMasterError
from src.paper.reconciliation.billing import billing_period
from src.paper.reconciliation.contracts import (
    APDecision,
    InvoiceCaseVersion,
    InvoicePackage,
    ReconciliationAssessment,
)
from src.paper.reconciliation.engine import ReconciliationEngine
from src.paper.reconciliation.fingerprints import (
    assessment_fingerprint,
    duplicate_key,
    installment_duplicate_key,
    policy_fingerprint,
)
from src.paper.reconciliation.ports import BaseInvoiceCaseRepository
from src.paper.reconciliation.settings import ReconciliationSettings
from src.paper.service import AgreementMasterService

_T = TypeVar("_T")
_logger = structlog.get_logger(__name__)


class _CaseReference(_Contract):
    case_id: Identifier
    version_number: int = Field(gt=0)


class _Page(_Contract):
    limit: int = Field(default=100, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class InvoiceCaseService:
    """Orchestrate independent rules, agreement authority, and case storage.

    The host supplies trusted actors, all dependencies, and transaction ownership.
    Case storage and agreement reads must share a transaction for AP publication.
    No model is selected or created by this service.
    """

    def __init__(
        self,
        repository: BaseInvoiceCaseRepository,
        *,
        master: AgreementMasterService,
        engine: ReconciliationEngine,
        settings: ReconciliationSettings,
    ) -> None:
        """Inject lifecycle storage, approved references, and configured rules.

        Args:
            repository: Tenant-scoped atomic case adapter.
            master: Approved agreement service with injected storage.
            engine: Pure deterministic rules with no external I/O.
            settings: Host-owned timeout and AP publication policy.
        """
        self._repository = repository
        self._master = master
        self._engine = engine
        self._settings = ReconciliationSettings.model_validate(settings.model_dump(mode="json"))

    async def _run(self, operation: Awaitable[_T]) -> _T:
        try:
            return await asyncio.wait_for(operation, self._settings.repository_timeout_seconds)
        except asyncio.TimeoutError:
            raise AgreementMasterError(
                "timeout", "Invoice case storage exceeded its deadline."
            ) from None

    async def _assess(
        self, actor: AgreementActor, package: InvoicePackage
    ) -> ReconciliationAssessment:
        fields = package.invoice.fields
        first, last = fields.service_period_start, fields.service_period_end
        if "installments" in self._settings.enabled_rules:
            first, last = billing_period(package)
        start: AgreementVersion | None = None
        end: AgreementVersion | None = None
        if first is not None and last is not None:
            # Sequential reads support a shared async session and transaction.
            start = await self._run(
                self._master.find_approved(
                    actor=actor,
                    lookup=AgreementLookup(identity=package.identity, as_of=first),
                )
            )
            end = await self._run(
                self._master.find_approved(
                    actor=actor,
                    lookup=AgreementLookup(identity=package.identity, as_of=last),
                )
            )
        assessment = self._engine.assess(
            package, agreement_start=start, agreement_end=end, tenant_id=actor.tenant_id
        )
        if self._engine.settings_fingerprint != policy_fingerprint(self._settings):
            raise AgreementMasterError(
                "invalid_configuration", "Case workflow and rule policies must agree."
            )
        return assessment

    async def create_case(
        self,
        *,
        actor: AgreementActor,
        package: InvoicePackage,
    ) -> InvoiceCaseVersion:
        """Assess a manually supplied package and persist its initial case.

        Args:
            actor: Trusted author and tenant supplied by the host.
            package: Typed source fields, document roles, and source references.

        Returns:
            Stored assessment with any atomic same-tenant duplicate disposition.
        """
        actor = AgreementActor.model_validate(actor)
        package = InvoicePackage.model_validate(package)
        assessment = await self._assess(actor, package)
        result = await self._run(
            self._repository.create(
                package=package,
                assessment=assessment,
                duplicate_key=duplicate_key(package),
                actor=actor,
            )
        )
        _logger.info("invoice_case_created", case_id=result.case_id, version=result.version_number)
        return result

    async def revise_case(
        self,
        *,
        actor: AgreementActor,
        case_id: str,
        expected_version: int,
        package: InvoicePackage,
    ) -> InvoiceCaseVersion:
        """Append corrected documents and current reconciliation findings.

        Args:
            actor: Trusted author and tenant supplied by the host.
            case_id: Existing case identifier.
            expected_version: Latest case version reviewed by the author.
            package: Updated source package with the same canonical identity.

        Returns:
            A new undecided version; earlier AP records remain historical.
        """
        actor = AgreementActor.model_validate(actor)
        reference = _CaseReference(case_id=case_id, version_number=expected_version)
        package = InvoicePackage.model_validate(package)
        previous = await self.get_version(
            actor=actor, case_id=reference.case_id, version_number=reference.version_number
        )
        if package.identity != previous.package.identity:
            raise AgreementMasterError(
                "invalid_agreement", "Canonical case identity cannot change."
            )
        assessment = await self._assess(actor, package)
        result = await self._run(
            self._repository.append(
                case_id=reference.case_id,
                package=package,
                assessment=assessment,
                duplicate_key=duplicate_key(package),
                expected_version=reference.version_number,
                actor=actor,
            )
        )
        _logger.info("invoice_case_revised", case_id=result.case_id, version=result.version_number)
        return result

    async def get_version(
        self,
        *,
        actor: AgreementActor,
        case_id: str,
        version_number: int,
    ) -> InvoiceCaseVersion:
        """Read an exact case version within the actor's tenant.

        Args:
            actor: Trusted tenant identity.
            case_id: Case identifier to read.
            version_number: Exact historical version.

        Returns:
            Draft or decided case version; absent scoped records raise not-found.
        """
        actor = AgreementActor.model_validate(actor)
        reference = _CaseReference(case_id=case_id, version_number=version_number)
        result = await self._run(
            self._repository.get_version(
                tenant_id=actor.tenant_id,
                case_id=reference.case_id,
                version_number=reference.version_number,
            )
        )
        if result is None or (
            result.tenant_id != actor.tenant_id
            or result.case_id != reference.case_id
            or result.version_number != reference.version_number
        ):
            raise AgreementMasterError("not_found", "Invoice case version was not found.")
        return InvoiceCaseVersion.model_validate(result)

    async def list_versions(
        self,
        *,
        actor: AgreementActor,
        case_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[InvoiceCaseVersion, ...]:
        """Read paginated case history newest first within the actor's tenant.

        Args:
            actor: Trusted tenant identity.
            case_id: Case identifier to read.
            limit: Page size between one and 100.
            offset: Nonnegative number of versions to skip.

        Returns:
            Stored historical versions; absent cases raise not-found.
        """
        actor = AgreementActor.model_validate(actor)
        page = _Page(limit=limit, offset=offset)
        first = await self.get_version(actor=actor, case_id=case_id, version_number=1)
        return await self._run(
            self._repository.list_versions(
                tenant_id=actor.tenant_id,
                case_id=first.case_id,
                limit=page.limit,
                offset=page.offset,
            )
        )

    async def list_cases(
        self,
        *,
        actor: AgreementActor,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[InvoiceCaseVersion, ...]:
        """Read current case versions within the actor's tenant.

        Args:
            actor: Trusted tenant identity.
            limit: Page size between one and 100.
            offset: Nonnegative number of cases to skip.

        Returns:
            Latest versions, newest created case first.
        """
        actor = AgreementActor.model_validate(actor)
        page = _Page(limit=limit, offset=offset)
        return await self._run(
            self._repository.list_latest(
                tenant_id=actor.tenant_id,
                limit=page.limit,
                offset=page.offset,
            )
        )

    async def decide_case(
        self,
        *,
        actor: AgreementActor,
        case_id: str,
        expected_version: int,
        decision: APDecision,
    ) -> InvoiceCaseVersion:
        """Record an authorized AP disposition for the exact current case.

        Args:
            actor: Trusted AP authority and tenant identity.
            case_id: Case identifier to decide.
            expected_version: Exact latest case version reviewed by AP.
            decision: Action, reason, and explicitly accepted configured findings.

        Returns:
            Stored version with immutable reviewer identity/time and decision.

        Raises:
            AgreementMasterError: Missing authority, stale case/reference/policy,
                duplicate package, or unresolved nonoverridable findings.
        """
        actor = AgreementActor.model_validate(actor)
        decision = APDecision.model_validate(decision)
        if not actor.can_approve:
            raise AgreementMasterError("forbidden", "AP decision authority is required.")
        current = await self.get_version(
            actor=actor, case_id=case_id, version_number=expected_version
        )
        if current.decision is not None:
            raise AgreementMasterError("conflict", "This invoice case version is already decided.")
        if self._settings.require_independent_approval and current.created_by == actor.user_id:
            raise AgreementMasterError("forbidden", "An independent AP reviewer is required.")
        if decision.action == "approve" and current.duplicate_of is not None:
            raise AgreementMasterError(
                "invalid_approval", "Duplicate invoice cases cannot be approved."
            )
        if decision.action == "reject" and decision.override_codes:
            raise AgreementMasterError(
                "invalid_approval", "Rejections do not accept finding overrides."
            )
        pinned = current.assessment.agreement_reference
        await self._run(
            self._repository.lock_for_decision(
                case_id=current.case_id,
                expected_version=current.version_number,
                actor=actor,
                agreement_id=(
                    pinned.agreement_id if pinned and decision.action == "approve" else None
                ),
            )
        )
        if decision.action == "approve":
            fresh = await self._assess(actor, current.package)
            if assessment_fingerprint(fresh) != assessment_fingerprint(current.assessment):
                raise AgreementMasterError(
                    "conflict",
                    "Agreement authority or reconciliation policy changed; revise the case.",
                )
            if fresh.agreement_reference is None:
                raise AgreementMasterError(
                    "invalid_approval", "An approved agreement reference is required."
                )
            installment_claim = installment_duplicate_key(current.package)
            if installment_claim is not None:
                claim_owner = await self._run(
                    self._repository.duplicate_owner(
                        tenant_id=actor.tenant_id, duplicate_key=installment_claim
                    )
                )
                if claim_owner != current.case_id:
                    raise AgreementMasterError(
                        "invalid_approval",
                        "An eligible installment claim must belong to this case before approval; "
                        "correct and reassess the case.",
                    )
            unresolved = {finding.code for finding in fresh.findings}
            accepted = set(decision.override_codes)
            allowed = set(self._settings.override_codes)
            if accepted != unresolved or not accepted.issubset(allowed):
                raise AgreementMasterError(
                    "invalid_approval",
                    "Unresolved findings require permitted, explicit AP overrides.",
                )
        result = await self._run(
            self._repository.decide(
                case_id=current.case_id,
                expected_version=current.version_number,
                decision=decision,
                actor=actor,
            )
        )
        _logger.info("invoice_case_decided", case_id=result.case_id, version=result.version_number)
        return result
