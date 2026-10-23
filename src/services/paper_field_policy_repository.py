"""Async tenant-scoped storage and atomic policy revision updates."""

from datetime import datetime, timezone
from typing import Any, cast

from pydantic import TypeAdapter
from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.paper_field_policy import PaperFieldPolicy
from src.db.models.paper_field_policy_version import PaperFieldPolicyVersion
from src.db.models.tenant import Tenant
from src.paper.contracts import AgreementActor
from src.paper.contracts._base import Identifier
from src.paper.errors import AgreementMasterError
from src.paper.field_policy.repository import BaseFieldPolicyRepository
from src.paper.field_policy.request import UpdateFieldPolicyRequest
from src.paper.field_policy.version import FieldPolicyVersion


class SqlAlchemyFieldPolicyRepository(BaseFieldPolicyRepository):
    """Append policies in the host transaction; never commit inside storage."""

    def __init__(self, db: AsyncSession) -> None:
        """Inject the host-owned write-capable async session.

        Args:
            db: Session shared with host matching and decision transactions.
        """
        self._db = db

    async def _lock_tenant(self, tenant_id: str, *, read: bool) -> None:
        # A tenant row exists even before the first policy override. Shared locks
        # keep matching decisions and first-policy creation serializable too.
        found = await self._db.scalar(
            select(Tenant.id).where(Tenant.id == tenant_id).with_for_update(read=read)
        )
        if found is None:
            raise AgreementMasterError("not_found", "Matching policy tenant was not found.")

    async def get_latest(self, *, tenant_id: str) -> FieldPolicyVersion | None:
        """Read current requirements with tenant isolation and a transaction lock.

        Args:
            tenant_id: Validated tenant supplied by the host.

        Returns:
            Current immutable revision, or None for deployment defaults.
        """
        tenant_id = TypeAdapter(Identifier).validate_python(tenant_id)
        await self._lock_tenant(tenant_id, read=True)
        row = await self._db.scalar(
            select(PaperFieldPolicyVersion)
            .join(
                PaperFieldPolicy,
                (PaperFieldPolicy.tenant_id == PaperFieldPolicyVersion.tenant_id)
                & (PaperFieldPolicy.latest_revision == PaperFieldPolicyVersion.revision),
            )
            .where(PaperFieldPolicyVersion.tenant_id == tenant_id)
        )
        return self._materialize(row) if row is not None else None

    async def append(
        self, *, actor: AgreementActor, request: UpdateFieldPolicyRequest
    ) -> FieldPolicyVersion:
        """Guard concurrent edits and append immutable audit history.

        Args:
            actor: Trusted tenant identity and policy editing permission.
            request: Explicit tenant overrides and expected current revision.

        Returns:
            Appended revision with server-stamped author and UTC timestamp.

        Raises:
            AgreementMasterError: The actor is unauthorized or revision is stale.
        """
        actor = AgreementActor.model_validate(actor)
        request = UpdateFieldPolicyRequest.model_validate(request.model_dump(mode="json"))
        if not actor.can_approve:
            raise AgreementMasterError("forbidden", "Matching policy edit authority is required.")
        await self._lock_tenant(actor.tenant_id, read=False)
        row = PaperFieldPolicyVersion(
            tenant_id=actor.tenant_id,
            revision=request.expected_revision + 1,
            requirements=[item.model_dump(mode="json") for item in request.requirements],
            updated_by=actor.user_id,
            updated_at=datetime.now(timezone.utc),
        )
        try:
            async with self._db.begin_nested():
                if request.expected_revision == 0:
                    self._db.add(PaperFieldPolicy(tenant_id=actor.tenant_id, latest_revision=1))
                    await self._db.flush()
                else:
                    result = cast(
                        CursorResult[Any],
                        await self._db.execute(
                            update(PaperFieldPolicy)
                            .where(
                                PaperFieldPolicy.tenant_id == actor.tenant_id,
                                PaperFieldPolicy.latest_revision == request.expected_revision,
                            )
                            .values(latest_revision=row.revision)
                            .execution_options(synchronize_session=False)
                        ),
                    )
                    if result.rowcount != 1:
                        raise AgreementMasterError(
                            "conflict", "Matching requirements changed; reload them before saving."
                        )
                self._db.add(row)
                await self._db.flush()
        except IntegrityError:
            raise AgreementMasterError(
                "conflict", "Matching requirements changed; reload them before saving."
            ) from None
        return self._materialize(row)

    @staticmethod
    def _materialize(row: PaperFieldPolicyVersion) -> FieldPolicyVersion:
        return FieldPolicyVersion.model_validate(
            {
                "tenant_id": row.tenant_id,
                "revision": row.revision,
                "requirements": row.requirements,
                "updated_by": row.updated_by,
                "updated_at": (
                    row.updated_at.replace(tzinfo=timezone.utc)
                    if row.updated_at.tzinfo is None
                    else row.updated_at
                ),
            }
        )
