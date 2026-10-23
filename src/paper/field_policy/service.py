"""Shared effective requirements for Settings, readiness and actual matching."""

import asyncio
import hashlib
import json
from collections.abc import Awaitable
from typing import TypeVar

import structlog
from pydantic import TypeAdapter

from src.paper.contracts import AgreementActor
from src.paper.contracts._base import Identifier
from src.paper.errors import AgreementMasterError
from src.paper.readiness._schemas import DocumentRole
from src.paper.reconciliation.settings import ReconciliationSettings

from .catalog import FieldPolicyCatalog
from .repository import BaseFieldPolicyRepository
from .request import UpdateFieldPolicyRequest
from .version import FieldPolicyVersion

_T = TypeVar("_T")
_logger = structlog.get_logger(__name__)
_ROLES: tuple[DocumentRole, ...] = (
    "rent_invoice",
    "tax_invoice",
    "utility_statement",
    "supporting_document",
)


class FieldPolicyService:
    """Overlay field presence only; accounting authority remains host-owned."""

    def __init__(self, repository: BaseFieldPolicyRepository, base: ReconciliationSettings) -> None:
        """Inject async storage and validated deployment policy.

        Args:
            repository: Tenant-scoped async persistence in the host transaction.
            base: Deployment-owned accounting and presence configuration.
        """
        self._repository = repository
        self._base = ReconciliationSettings.model_validate(base.model_dump(mode="json"))

    async def _run(self, operation: Awaitable[_T]) -> _T:
        try:
            return await asyncio.wait_for(operation, timeout=self._base.repository_timeout_seconds)
        except asyncio.TimeoutError:
            raise AgreementMasterError(
                "timeout", "Document matching policy storage exceeded its deadline."
            ) from None

    async def _latest(self, tenant_id: str) -> FieldPolicyVersion | None:
        tenant_id = TypeAdapter(Identifier).validate_python(tenant_id)
        version = await self._run(self._repository.get_latest(tenant_id=tenant_id))
        if version is not None:
            version = FieldPolicyVersion.model_validate(version.model_dump(mode="json"))
            if version.tenant_id != tenant_id:
                raise AgreementMasterError("not_found", "Matching policy was not found.")
        return version

    def _effective(self, version: FieldPolicyVersion | None) -> ReconciliationSettings:
        if version is None:
            return self._base
        payload = self._base.model_dump(mode="json")
        # The complete base policy is bound, including changes to YAML requirements.
        encoded = json.dumps(
            {"base": payload, "override": version.model_dump(mode="json")},
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )
        digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
        merged = {(item.role, item.field): item for item in self._base.field_requirements}
        merged.update({(item.role, item.field): item for item in version.requirements})
        payload.update(
            field_requirements=[item.model_dump(mode="json") for item in merged.values()],
            policy_version=f"fields.{version.revision}.{digest}",
        )
        return ReconciliationSettings.model_validate(payload)

    def _catalog(
        self, actor: AgreementActor, version: FieldPolicyVersion | None
    ) -> FieldPolicyCatalog:
        from src.paper.readiness.requirements import effective_requirements

        settings = self._effective(version)
        return FieldPolicyCatalog(
            revision=version.revision if version else 0,
            policy_id=settings.policy_id,
            policy_version=settings.policy_version,
            can_edit=actor.can_approve,
            requirements=tuple(
                item for role in _ROLES for item in effective_requirements(settings, role)
            ),
            base_requirements=tuple(
                item for role in _ROLES for item in effective_requirements(self._base, role)
            ),
            overrides=version.requirements if version else (),
            updated_by=version.updated_by if version else None,
            updated_at=version.updated_at if version else None,
        )

    async def effective(self, *, tenant_id: str) -> ReconciliationSettings:
        """Resolve current policy without caching overrides across requests.

        Args:
            tenant_id: Tenant supplied by trusted host authentication.

        Returns:
            Shared configuration for readiness, reconciliation and AP decisions.
        """
        return self._effective(await self._latest(tenant_id))

    async def read(self, *, actor: AgreementActor) -> FieldPolicyCatalog:
        """Read effective guidance and server-established edit capability.

        Args:
            actor: Trusted tenant identity and persisted reviewer permission.

        Returns:
            Effective and inherited guidance alongside explicit tenant overrides.
        """
        actor = AgreementActor.model_validate(actor)
        return self._catalog(actor, await self._latest(actor.tenant_id))

    async def update(
        self, *, actor: AgreementActor, request: UpdateFieldPolicyRequest
    ) -> FieldPolicyCatalog:
        """Append reviewed policy changes; the caller owns commit and rollback.

        Args:
            actor: Trusted tenant identity with persisted AP review authority.
            request: Complete replacement of explicit tenant field overrides.

        Returns:
            Updated effective policy with server-stamped audit provenance.

        Raises:
            AgreementMasterError: Editing is forbidden, stale or times out.
        """
        actor = AgreementActor.model_validate(actor)
        request = UpdateFieldPolicyRequest.model_validate(request.model_dump(mode="json"))
        if not actor.can_approve:
            raise AgreementMasterError(
                "forbidden", "AP review authority is required to edit matching requirements."
            )
        version = await self._run(self._repository.append(actor=actor, request=request))
        version = FieldPolicyVersion.model_validate(version.model_dump(mode="json"))
        if (
            version.tenant_id != actor.tenant_id
            or version.revision != request.expected_revision + 1
        ):
            raise AgreementMasterError("conflict", "Matching policy revision is inconsistent.")
        _logger.info("paper_field_policy_updated", revision=version.revision)
        return self._catalog(actor, version)
