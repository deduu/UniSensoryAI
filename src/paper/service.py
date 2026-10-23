"""Agreement lifecycle service without database, web, or inference dependencies."""

import asyncio
from collections.abc import Awaitable
from typing import TypeVar

import structlog
from pydantic import Field, TypeAdapter

from src.paper.contracts import (
    AgreementActor,
    AgreementDraft,
    AgreementIdentity,
    AgreementLookup,
    AgreementVersion,
    ApprovalDecision,
)
from src.paper.contracts._base import Identifier, _Contract
from src.paper.errors import AgreementMasterError
from src.paper.parties import BasePartyRoleValidator, DeterministicPartyRoleValidator
from src.paper.ports import BaseAgreementRepository
from src.paper.settings import AgreementMasterSettings

_T = TypeVar("_T")
_identifier = TypeAdapter(Identifier)
_logger = structlog.get_logger(__name__)
_IDENTITY_FIELDS = ("vendor_id", "store_id", "contract_number")


class _VersionReference(_Contract):
    agreement_id: Identifier
    version_number: int = Field(gt=0)


class _HistoryPage(_Contract):
    limit: int = Field(default=100, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class AgreementMasterService:
    """Create snapshots and explicitly publish approved master versions."""

    def __init__(
        self,
        repository: BaseAgreementRepository,
        *,
        settings: AgreementMasterSettings | None = None,
        party_role_validator: BasePartyRoleValidator | None = None,
    ) -> None:
        """Inject storage and publication policy.

        Args:
            repository: Adapter with tenant-scoped, atomic persistence operations.
            settings: Host-owned policy; no model is constructed by this service.
            party_role_validator: Injected source-role policy, independent of models.
        """
        self._repository = repository
        self._settings = AgreementMasterSettings.model_validate(
            (settings or AgreementMasterSettings()).model_dump(mode="json")
        )
        self._party_role_validator = party_role_validator or DeterministicPartyRoleValidator()

    async def _run(self, operation: Awaitable[_T]) -> _T:
        try:
            return await asyncio.wait_for(operation, self._settings.repository_timeout_seconds)
        except asyncio.TimeoutError:
            raise AgreementMasterError(
                "timeout", "Agreement storage exceeded its deadline."
            ) from None

    @staticmethod
    def _check_identity(identity: AgreementIdentity, draft: AgreementDraft) -> None:
        for field in _IDENTITY_FIELDS:
            extracted = getattr(draft.terms, field)
            if extracted is not None and extracted != getattr(identity, field):
                raise AgreementMasterError(
                    "invalid_agreement", "Extracted terms disagree with master identity."
                )

    async def create_draft(
        self, *, actor: AgreementActor, identity: AgreementIdentity, draft: AgreementDraft
    ) -> AgreementVersion:
        """Create an unapproved agreement.

        Args:
            actor: Identity and tenant established by the host.
            identity: Canonical vendor, store, and contract identifiers.
            draft: Validated source terms and effective dates.

        Returns:
            Persisted initial draft version in the host transaction.
        """
        actor = AgreementActor.model_validate(actor)
        identity = AgreementIdentity.model_validate(identity)
        draft = AgreementDraft.model_validate(draft)
        self._check_identity(identity, draft)
        result = await self._run(
            self._repository.create(identity=identity, draft=draft, actor=actor)
        )
        _logger.info(
            "agreement_draft_created",
            agreement_id=result.agreement_id,
            version=result.version_number,
        )
        return result

    async def revise(
        self,
        *,
        actor: AgreementActor,
        agreement_id: str,
        expected_version: int,
        draft: AgreementDraft,
    ) -> AgreementVersion:
        """Append terms while retaining prior snapshots.

        Args:
            actor: Trusted tenant and author identity.
            agreement_id: Existing agreement identifier.
            expected_version: Latest version the caller has reviewed.
            draft: New source terms and a change reason.

        Returns:
            A new draft version; previous approval remains attached to its version.
        """
        actor = AgreementActor.model_validate(actor)
        reference = _VersionReference(agreement_id=agreement_id, version_number=expected_version)
        draft = AgreementDraft.model_validate(draft)
        previous = await self.get_version(
            actor=actor,
            agreement_id=reference.agreement_id,
            version_number=reference.version_number,
        )
        self._check_identity(previous.identity, draft)
        if (
            "party_roles" in previous.draft.terms.extensions
            and "party_roles" not in draft.terms.extensions
        ):
            raise AgreementMasterError(
                "invalid_agreement",
                "Saved party roles must remain available across revisions; "
                "retain and correct the source roles rather than removing them.",
            )
        previous_schedule = previous.draft.terms.installment_schedule
        if previous_schedule is not None:
            retained_ids = (
                {item.installment_id for item in draft.terms.installment_schedule.installments}
                if draft.terms.installment_schedule is not None
                else set()
            )
            if not {item.installment_id for item in previous_schedule.installments}.issubset(
                retained_ids
            ):
                raise AgreementMasterError(
                    "invalid_agreement",
                    "Saved installment identifiers must remain stable across revisions; "
                    "correct the existing obligation rather than renaming or removing it.",
                )
        result = await self._run(
            self._repository.append(
                agreement_id=reference.agreement_id,
                draft=draft,
                expected_version=reference.version_number,
                actor=actor,
            )
        )
        _logger.info(
            "agreement_draft_revised",
            agreement_id=result.agreement_id,
            version=result.version_number,
        )
        return result

    async def approve(
        self,
        *,
        actor: AgreementActor,
        agreement_id: str,
        version_number: int,
        decision: ApprovalDecision,
    ) -> AgreementVersion:
        """Publish the current snapshot with an explicit accounting decision.

        Assigned identity satisfies identifier presence without populating absent
        source identifiers. Any contradictory extracted identifier is rejected.

        Args:
            actor: Host-authorized approver identity.
            agreement_id: Agreement to publish.
            version_number: Exact version reviewed; storage rejects stale approval.
            decision: Classification, rule reference, and reviewer reason.

        Returns:
            Approved version with immutable publication audit.
        """
        actor = AgreementActor.model_validate(actor)
        decision = ApprovalDecision.model_validate(decision)
        if not actor.can_approve:
            raise AgreementMasterError("forbidden", "Agreement approval authority is required.")
        current = await self.get_version(
            actor=actor, agreement_id=agreement_id, version_number=version_number
        )
        if current.approval is not None:
            raise AgreementMasterError("conflict", "This agreement version is already approved.")
        if self._settings.require_independent_approval and current.created_by == actor.user_id:
            raise AgreementMasterError(
                "forbidden", "An independent agreement approver is required."
            )
        identity = AgreementIdentity.model_validate(current.identity)
        self._check_identity(identity, current.draft)
        required = self._settings.required_agreement_fields
        if current.draft.terms.rent_type:
            required += self._settings.required_fields_by_rent_type.get(
                current.draft.terms.rent_type, ()
            )
        if any(
            getattr(identity if name in _IDENTITY_FIELDS else current.draft.terms, name)
            in (None, "", (), [], {})
            for name in required
        ):
            raise AgreementMasterError("invalid_approval", "Required agreement terms are missing.")
        if "party_roles" in current.draft.terms.extensions:
            issues = self._party_role_validator.validate(
                current.draft.terms,
                tuple(
                    item.evidence
                    for item in current.draft.evidence
                    if item.document_id in current.draft.source_document_ids
                ),
            )
            if any(issue.code != "party_roles_review_required" for issue in issues):
                raise AgreementMasterError(
                    "invalid_approval",
                    "Party roles or their source evidence remain unresolved; "
                    "correct the draft before approval.",
                )
            if not decision.acknowledge_party_roles:
                raise AgreementMasterError(
                    "invalid_approval",
                    "Party roles require explicit review acknowledgement before publication.",
                )
        elif decision.acknowledge_party_roles:
            # An old draft has no roles to review; never create a misleading audit.
            decision = decision.model_copy(update={"acknowledge_party_roles": False})
        if current.draft.extraction_warnings and not decision.acknowledge_extraction_warnings:
            raise AgreementMasterError(
                "invalid_approval", "Extraction warnings require explicit review acknowledgement."
            )
        result = await self._run(
            self._repository.approve(
                agreement_id=current.agreement_id,
                version_number=current.version_number,
                decision=decision,
                actor=actor,
            )
        )
        _logger.info(
            "agreement_version_approved",
            agreement_id=result.agreement_id,
            version=result.version_number,
        )
        return result

    async def get_version(
        self, *, actor: AgreementActor, agreement_id: str, version_number: int
    ) -> AgreementVersion:
        """Read a version within the actor's tenant.

        Args:
            actor: Trusted tenant identity.
            agreement_id: Agreement identifier.
            version_number: Historical version to read.

        Returns:
            Draft or approved version, raising a safe not-found error otherwise.
        """
        actor = AgreementActor.model_validate(actor)
        reference = _VersionReference(agreement_id=agreement_id, version_number=version_number)
        result = await self._run(
            self._repository.get_version(
                tenant_id=actor.tenant_id,
                agreement_id=reference.agreement_id,
                version_number=reference.version_number,
            )
        )
        if result is None:
            raise AgreementMasterError("not_found", "Agreement version was not found.")
        return result

    async def list_versions(
        self, *, actor: AgreementActor, agreement_id: str, limit: int = 100, offset: int = 0
    ) -> tuple[AgreementVersion, ...]:
        """Read paginated version history within the actor's tenant.

        Args:
            actor: Trusted tenant identity.
            agreement_id: Agreement identifier.
            limit: At most 100 versions per page.
            offset: Number of historical versions to skip.

        Returns:
            Ordered versions; missing agreements raise not-found.
        """
        actor = AgreementActor.model_validate(actor)
        agreement_id = _identifier.validate_python(agreement_id)
        page = _HistoryPage(limit=limit, offset=offset)
        await self.get_version(actor=actor, agreement_id=agreement_id, version_number=1)
        return await self._run(
            self._repository.list_versions(
                tenant_id=actor.tenant_id,
                agreement_id=agreement_id,
                limit=page.limit,
                offset=page.offset,
            )
        )

    async def list_agreements(
        self, *, actor: AgreementActor, limit: int = 100, offset: int = 0
    ) -> tuple[AgreementVersion, ...]:
        """Read latest snapshots within the actor's tenant without approving them.

        Args:
            actor: Trusted tenant identity; approval authority is not required.
            limit: At most 100 agreements per page.
            offset: Number of agreements to skip.

        Returns:
            One latest snapshot per agreement, most recently revised first.
        """
        actor = AgreementActor.model_validate(actor)
        page = _HistoryPage(limit=limit, offset=offset)
        return await self._run(
            self._repository.list_latest(
                tenant_id=actor.tenant_id, limit=page.limit, offset=page.offset
            )
        )

    async def find_approved(
        self, *, actor: AgreementActor, lookup: AgreementLookup
    ) -> AgreementVersion | None:
        """Find approved reference data without exposing newer unapproved drafts.

        Args:
            actor: Trusted tenant identity.
            lookup: Exact identity and effective business date.

        Returns:
            Latest started approval if still effective; expired revisions return no match.
        """
        actor = AgreementActor.model_validate(actor)
        lookup = AgreementLookup.model_validate(lookup)
        return await self._run(
            self._repository.find_approved(tenant_id=actor.tenant_id, lookup=lookup)
        )
