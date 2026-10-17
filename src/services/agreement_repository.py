"""Async SQLAlchemy adapter for the model-independent agreement master."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Any, TypeVar, cast
from uuid import uuid4

from pydantic import BaseModel, Field, StringConstraints, TypeAdapter, ValidationError
from sqlalchemy import Select, and_, select, update
from sqlalchemy.engine import CursorResult, Row
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.agreement import Agreement
from src.db.models.agreement_approval import AgreementApproval
from src.db.models.agreement_version import AgreementVersion as AgreementVersionRow
from src.paper.contracts import (
    AgreementActor,
    AgreementDraft,
    AgreementIdentity,
    AgreementLookup,
    AgreementVersion,
    ApprovalDecision,
    ApprovalRecord,
)
from src.paper.errors import AgreementMasterError
from src.paper.ports import BaseAgreementRepository

_Model = TypeVar("_Model", bound=BaseModel)
_Identifier: TypeAdapter[str] = TypeAdapter(
    Annotated[
        str, StringConstraints(strict=True, strip_whitespace=True, min_length=1, max_length=128)
    ]
)
_Version: TypeAdapter[int] = TypeAdapter(Annotated[int, Field(strict=True, ge=1)])
_Limit: TypeAdapter[int] = TypeAdapter(Annotated[int, Field(strict=True, ge=1, le=100)])
_Offset: TypeAdapter[int] = TypeAdapter(Annotated[int, Field(strict=True, ge=0)])


def _validated_model(model: type[_Model], value: _Model) -> _Model:
    try:
        return model.model_validate(value)
    except ValidationError:
        raise AgreementMasterError("invalid_agreement", "Agreement input is invalid") from None


def _validated_identifier(value: str) -> str:
    try:
        return _Identifier.validate_python(value)
    except ValidationError:
        raise AgreementMasterError("invalid_agreement", "Agreement reference is invalid") from None


def _validated_integer(adapter: TypeAdapter[int], value: int) -> int:
    try:
        return adapter.validate_python(value)
    except ValidationError:
        raise AgreementMasterError("invalid_agreement", "Agreement query is invalid") from None


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


class SqlAlchemyAgreementRepository(BaseAgreementRepository):
    """Persist snapshots without taking ownership of the caller's transaction.

    Args:
        db: Injected async session. The caller commits or rolls back.
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create(
        self,
        *,
        identity: AgreementIdentity,
        draft: AgreementDraft,
        actor: AgreementActor,
    ) -> AgreementVersion:
        """Create a unique tenant-owned agreement and its first snapshot.

        Args:
            identity: Stable business identity resolved by the consuming system.
            draft: Validated terms and original source references.
            actor: Author identity and tenant scope.

        Returns:
            The newly persisted draft version.

        Raises:
            AgreementMasterError: The identity already exists.
        """
        identity = _validated_model(AgreementIdentity, identity)
        draft = _validated_model(AgreementDraft, draft)
        actor = _validated_model(AgreementActor, actor)
        header = Agreement(
            id=str(uuid4()),
            tenant_id=actor.tenant_id,
            vendor_id=identity.vendor_id,
            store_id=identity.store_id,
            contract_number=identity.contract_number,
            latest_version=1,
        )
        snapshot = self._snapshot(header.id, 1, draft, actor)
        try:
            async with self._db.begin_nested():
                self._db.add(header)
                await self._db.flush()
                self._db.add(snapshot)
                await self._db.flush()
        except IntegrityError:
            raise AgreementMasterError("conflict", "Agreement identity already exists") from None
        return self._materialize(header, snapshot, None)

    async def append(
        self,
        *,
        agreement_id: str,
        draft: AgreementDraft,
        expected_version: int,
        actor: AgreementActor,
    ) -> AgreementVersion:
        """Append a snapshot if the expected revision remains current.

        Args:
            agreement_id: Stable agreement identifier.
            draft: Replacement terms stored in a new immutable snapshot.
            expected_version: Revision the author reviewed before updating.
            actor: Author identity and tenant scope.

        Returns:
            The new draft version.

        Raises:
            AgreementMasterError: Revision, identity, or persistence conflict.
        """
        agreement_id = _validated_identifier(agreement_id)
        expected_version = _validated_integer(_Version, expected_version)
        draft = _validated_model(AgreementDraft, draft)
        actor = _validated_model(AgreementActor, actor)
        snapshot = self._snapshot(agreement_id, expected_version + 1, draft, actor)
        try:
            async with self._db.begin_nested():
                await self._guard_revision(
                    tenant_id=actor.tenant_id,
                    agreement_id=agreement_id,
                    expected_version=expected_version,
                    increment=True,
                )
                header = await self._header(actor.tenant_id, agreement_id)
                if header is None:
                    raise AgreementMasterError("conflict", "Agreement revision is unavailable")
                self._db.add(snapshot)
                await self._db.flush()
        except IntegrityError:
            raise AgreementMasterError(
                "conflict", "Agreement revision could not be saved"
            ) from None
        return self._materialize(header, snapshot, None)

    async def approve(
        self,
        *,
        agreement_id: str,
        version_number: int,
        decision: ApprovalDecision,
        actor: AgreementActor,
    ) -> AgreementVersion:
        """Approve the latest snapshot once, retaining the decision separately.

        Args:
            agreement_id: Stable agreement identifier.
            version_number: Latest revision reviewed by the approver.
            decision: Approved classification, rule version, and review reason.
            actor: Authorized approver identity and tenant scope.

        Returns:
            The approved version with immutable approval metadata.

        Raises:
            AgreementMasterError: Authorization, stale revision, or replay conflict.
        """
        agreement_id = _validated_identifier(agreement_id)
        version_number = _validated_integer(_Version, version_number)
        decision = _validated_model(ApprovalDecision, decision)
        actor = _validated_model(AgreementActor, actor)
        if not actor.can_approve:
            raise AgreementMasterError("forbidden", "Agreement approval permission is required")
        approval = AgreementApproval(
            tenant_id=actor.tenant_id,
            agreement_id=agreement_id,
            version_number=version_number,
            decision=decision.model_dump(mode="json"),
            approved_by=actor.user_id,
            approved_at=datetime.now(timezone.utc),
        )
        try:
            async with self._db.begin_nested():
                # This UPDATE takes the same row lock as append, even when the
                # revision value does not change. Approval cannot race a revision.
                await self._guard_revision(
                    tenant_id=actor.tenant_id,
                    agreement_id=agreement_id,
                    expected_version=version_number,
                    increment=False,
                )
                row = (
                    await self._db.execute(
                        self._version_query()
                        .where(
                            AgreementVersionRow.tenant_id == actor.tenant_id,
                            AgreementVersionRow.agreement_id == agreement_id,
                            AgreementVersionRow.version_number == version_number,
                        )
                        .limit(1)
                    )
                ).first()
                if row is None:
                    raise AgreementMasterError("conflict", "Agreement revision is unavailable")
                header, snapshot, existing = row
                if existing is not None:
                    raise AgreementMasterError("conflict", "Agreement revision is already approved")
                self._db.add(approval)
                await self._db.flush()
        except IntegrityError:
            raise AgreementMasterError(
                "conflict", "Agreement revision is already approved"
            ) from None
        return self._materialize(header, snapshot, approval)

    async def get_version(
        self, *, tenant_id: str, agreement_id: str, version_number: int
    ) -> AgreementVersion | None:
        """Read a single snapshot using mandatory tenant scope.

        Args:
            tenant_id: Tenant permitted to access the agreement.
            agreement_id: Stable agreement identifier.
            version_number: Exact immutable snapshot number.

        Returns:
            A snapshot, or None if it does not exist within the tenant.
        """
        tenant_id = _validated_identifier(tenant_id)
        agreement_id = _validated_identifier(agreement_id)
        version_number = _validated_integer(_Version, version_number)
        result = await self._db.execute(
            self._version_query().where(
                AgreementVersionRow.tenant_id == tenant_id,
                AgreementVersionRow.agreement_id == agreement_id,
                AgreementVersionRow.version_number == version_number,
            )
        )
        row = result.first()
        return self._from_row(row) if row is not None else None

    async def list_versions(
        self, *, tenant_id: str, agreement_id: str, limit: int = 100, offset: int = 0
    ) -> tuple[AgreementVersion, ...]:
        """Read tenant-owned snapshots in descending version order.

        Args:
            tenant_id: Tenant permitted to access the agreement.
            agreement_id: Stable agreement identifier.
            limit: Maximum number of results.
            offset: Number of results to skip.

        Returns:
            Immutable snapshots, with approvals included when present.
        """
        tenant_id = _validated_identifier(tenant_id)
        agreement_id = _validated_identifier(agreement_id)
        limit = _validated_integer(_Limit, limit)
        offset = _validated_integer(_Offset, offset)
        result = await self._db.execute(
            self._version_query()
            .where(
                AgreementVersionRow.tenant_id == tenant_id,
                AgreementVersionRow.agreement_id == agreement_id,
            )
            .order_by(AgreementVersionRow.version_number.desc())
            .limit(limit)
            .offset(offset)
        )
        return tuple(self._from_row(row) for row in result.all())

    async def list_latest(
        self, *, tenant_id: str, limit: int = 100, offset: int = 0
    ) -> tuple[AgreementVersion, ...]:
        """Read one latest snapshot per tenant-owned agreement with stable pages.

        Args:
            tenant_id: Tenant permitted to access the agreement queue.
            limit: Page size between one and 100.
            offset: Nonnegative number of agreements to skip.

        Returns:
            Snapshots ordered by latest creation time and agreement identifier.
        """
        tenant_id = _validated_identifier(tenant_id)
        limit = _validated_integer(_Limit, limit)
        offset = _validated_integer(_Offset, offset)
        result = await self._db.execute(
            self._version_query()
            .where(
                Agreement.tenant_id == tenant_id,
                Agreement.latest_version == AgreementVersionRow.version_number,
            )
            .order_by(AgreementVersionRow.created_at.desc(), Agreement.id.desc())
            .limit(limit)
            .offset(offset)
        )
        return tuple(self._from_row(row) for row in result.all())

    async def find_approved(
        self, *, tenant_id: str, lookup: AgreementLookup
    ) -> AgreementVersion | None:
        """Find the authoritative approved revision on the requested date.

        Args:
            tenant_id: Tenant permitted to consume the master record.
            lookup: Business identity and date requiring approved terms.

        Returns:
            The highest approved revision that has started, when it remains
            effective. An ended amendment does not revive older terms. Future
            revisions and unapproved drafts do not hide earlier authority.
        """
        tenant_id = _validated_identifier(tenant_id)
        lookup = _validated_model(AgreementLookup, lookup)
        result = await self._db.execute(
            self._version_query(approved_only=True)
            .where(
                AgreementVersionRow.tenant_id == tenant_id,
                Agreement.vendor_id == lookup.identity.vendor_id,
                Agreement.store_id == lookup.identity.store_id,
                Agreement.contract_number == lookup.identity.contract_number,
                AgreementVersionRow.effective_from <= lookup.as_of,
            )
            .order_by(AgreementVersionRow.version_number.desc())
            .limit(1)
        )
        row = result.first()
        if row is None:
            return None
        authoritative = self._from_row(row)
        return authoritative if authoritative.draft.effective_to >= lookup.as_of else None

    async def _guard_revision(
        self, *, tenant_id: str, agreement_id: str, expected_version: int, increment: bool
    ) -> None:
        revision = expected_version + 1 if increment else expected_version
        result = cast(
            CursorResult[Any],
            await self._db.execute(
                update(Agreement)
                .where(
                    Agreement.tenant_id == tenant_id,
                    Agreement.id == agreement_id,
                    Agreement.latest_version == expected_version,
                )
                .values(latest_version=revision)
                .execution_options(synchronize_session=False)
            ),
        )
        if result.rowcount != 1:
            raise AgreementMasterError("conflict", "Agreement revision is stale or unavailable")

    async def _header(self, tenant_id: str, agreement_id: str) -> Agreement | None:
        result = await self._db.execute(
            select(Agreement)
            .where(Agreement.tenant_id == tenant_id, Agreement.id == agreement_id)
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    @staticmethod
    def _snapshot(
        agreement_id: str, version_number: int, draft: AgreementDraft, actor: AgreementActor
    ) -> AgreementVersionRow:
        return AgreementVersionRow(
            tenant_id=actor.tenant_id,
            agreement_id=agreement_id,
            version_number=version_number,
            effective_from=draft.effective_from,
            effective_to=draft.effective_to,
            draft=draft.model_dump(mode="json"),
            created_by=actor.user_id,
            created_at=datetime.now(timezone.utc),
        )

    @staticmethod
    def _version_query(
        *, approved_only: bool = False
    ) -> Select[tuple[Agreement, AgreementVersionRow, AgreementApproval]]:
        statement = select(Agreement, AgreementVersionRow, AgreementApproval).join(
            AgreementVersionRow,
            and_(
                Agreement.tenant_id == AgreementVersionRow.tenant_id,
                Agreement.id == AgreementVersionRow.agreement_id,
            ),
        )
        join_condition = and_(
            AgreementVersionRow.tenant_id == AgreementApproval.tenant_id,
            AgreementVersionRow.agreement_id == AgreementApproval.agreement_id,
            AgreementVersionRow.version_number == AgreementApproval.version_number,
        )
        return statement.join(AgreementApproval, join_condition, isouter=not approved_only)

    @classmethod
    def _from_row(cls, row: Row[Any]) -> AgreementVersion:
        header, snapshot, approval = row
        return cls._materialize(header, snapshot, approval)

    @staticmethod
    def _materialize(
        header: Agreement, snapshot: AgreementVersionRow, approval: AgreementApproval | None
    ) -> AgreementVersion:
        record = (
            ApprovalRecord(
                **approval.decision,
                approved_by=approval.approved_by,
                approved_at=_aware(approval.approved_at),
            )
            if approval is not None
            else None
        )
        return AgreementVersion(
            agreement_id=header.id,
            tenant_id=header.tenant_id,
            version_number=snapshot.version_number,
            identity=AgreementIdentity(
                vendor_id=header.vendor_id,
                store_id=header.store_id,
                contract_number=header.contract_number,
            ),
            draft=AgreementDraft.model_validate(snapshot.draft),
            created_by=snapshot.created_by,
            created_at=_aware(snapshot.created_at),
            approval=record,
        )
