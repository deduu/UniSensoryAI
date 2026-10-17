"""Async storage adapter for model-independent PAPER reconciliation cases."""

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
from src.db.models.invoice_case import InvoiceCase
from src.db.models.invoice_case_decision import InvoiceCaseDecision
from src.db.models.invoice_case_version import InvoiceCaseVersion as InvoiceCaseVersionRow
from src.db.models.invoice_duplicate_claim import InvoiceDuplicateClaim
from src.paper.contracts import AgreementActor, AgreementIdentity
from src.paper.errors import AgreementMasterError
from src.paper.reconciliation.contracts import (
    APDecision,
    APDecisionRecord,
    InvoiceCaseVersion,
    InvoicePackage,
    ReconciliationAssessment,
)
from src.paper.reconciliation.fingerprints import installment_duplicate_key
from src.paper.reconciliation.ports.case_repository import BaseInvoiceCaseRepository

_Model = TypeVar("_Model", bound=BaseModel)
_Identifier: TypeAdapter[str] = TypeAdapter(
    Annotated[
        str, StringConstraints(strict=True, strip_whitespace=True, min_length=1, max_length=128)
    ]
)
_Digest: TypeAdapter[str] = TypeAdapter(
    Annotated[str, StringConstraints(strict=True, pattern=r"^[a-f0-9]{64}$")]
)
_Version: TypeAdapter[int] = TypeAdapter(Annotated[int, Field(strict=True, ge=1)])
_Limit: TypeAdapter[int] = TypeAdapter(Annotated[int, Field(strict=True, ge=1, le=100)])
_Offset: TypeAdapter[int] = TypeAdapter(Annotated[int, Field(strict=True, ge=0)])


def _validated_model(model: type[_Model], value: _Model) -> _Model:
    try:
        return model.model_validate(value.model_dump(mode="json"))
    except ValidationError:
        raise AgreementMasterError("invalid_agreement", "Invoice case input is invalid") from None


def _validated(adapter: TypeAdapter[Any], value: Any) -> Any:
    try:
        return adapter.validate_python(value)
    except ValidationError:
        raise AgreementMasterError(
            "invalid_agreement", "Invoice case reference is invalid"
        ) from None


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


class SqlAlchemyInvoiceCaseRepository(BaseInvoiceCaseRepository):
    """Persist case snapshots and decisions in the caller's transaction.

    Args:
        db: Injected async session; the host owns commit and rollback.
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create(
        self,
        *,
        package: InvoicePackage,
        assessment: ReconciliationAssessment,
        duplicate_key: str | None,
        actor: AgreementActor,
    ) -> InvoiceCaseVersion:
        """Create a durable case, reserving a tenant duplicate key atomically.

        Args:
            package: Validated external document package and canonical identity.
            assessment: Deterministic assessment retained with its policy version.
            duplicate_key: SHA-256 business key, when enough source identity exists.
            actor: Trusted author and tenant context.

        Returns:
            The first case revision, including a duplicate owner if applicable.

        Raises:
            AgreementMasterError: Invalid input or persistence conflict.
        """
        package = _validated_model(InvoicePackage, package)
        assessment = _validated_model(ReconciliationAssessment, assessment)
        actor = _validated_model(AgreementActor, actor)
        duplicate_key = _validated(_Digest, duplicate_key) if duplicate_key is not None else None
        header = InvoiceCase(
            id=str(uuid4()),
            tenant_id=actor.tenant_id,
            vendor_id=package.identity.vendor_id,
            store_id=package.identity.store_id,
            contract_number=package.identity.contract_number,
            latest_version=1,
            created_at=datetime.now(timezone.utc),
        )
        try:
            async with self._db.begin_nested():
                self._db.add(header)
                await self._db.flush()
                duplicate_of = await self._reserve_duplicate(
                    actor.tenant_id, duplicate_key, header.id
                )
                if duplicate_of is None:
                    duplicate_of = await self._reserve_installment(
                        package, assessment, actor.tenant_id, header.id
                    )
                snapshot = self._snapshot(header.id, 1, package, assessment, duplicate_of, actor)
                self._db.add(snapshot)
                await self._db.flush()
        except IntegrityError:
            raise AgreementMasterError("conflict", "Invoice case could not be saved") from None
        return self._materialize(header, snapshot, None)

    async def append(
        self,
        *,
        case_id: str,
        package: InvoicePackage,
        assessment: ReconciliationAssessment,
        duplicate_key: str | None,
        expected_version: int,
        actor: AgreementActor,
    ) -> InvoiceCaseVersion:
        """Append an immutable revision when its expected version is current.

        Args:
            case_id: Stable case identifier.
            package: Replacement package with unchanged canonical identity.
            assessment: Assessment for the replacement package.
            duplicate_key: New or retained SHA-256 business key.
            expected_version: Latest revision the author reviewed.
            actor: Trusted author and tenant context.

        Returns:
            The new case snapshot; all earlier versions and claims remain intact.

        Raises:
            AgreementMasterError: Stale version, changed identity, or persistence conflict.
        """
        case_id = _validated(_Identifier, case_id)
        expected_version = _validated(_Version, expected_version)
        package = _validated_model(InvoicePackage, package)
        assessment = _validated_model(ReconciliationAssessment, assessment)
        actor = _validated_model(AgreementActor, actor)
        duplicate_key = _validated(_Digest, duplicate_key) if duplicate_key is not None else None
        try:
            async with self._db.begin_nested():
                await self._guard_revision(
                    actor.tenant_id, case_id, expected_version, increment=True
                )
                header = await self._header(actor.tenant_id, case_id)
                if header is None or self._identity(header) != package.identity:
                    raise AgreementMasterError("conflict", "Invoice case identity cannot change")
                duplicate_of = await self._reserve_duplicate(
                    actor.tenant_id, duplicate_key, case_id
                )
                if duplicate_of is None:
                    duplicate_of = await self._reserve_installment(
                        package, assessment, actor.tenant_id, case_id
                    )
                snapshot = self._snapshot(
                    case_id, expected_version + 1, package, assessment, duplicate_of, actor
                )
                self._db.add(snapshot)
                await self._db.flush()
        except IntegrityError:
            raise AgreementMasterError(
                "conflict", "Invoice case revision could not be saved"
            ) from None
        return self._materialize(header, snapshot, None)

    async def get_version(
        self, *, tenant_id: str, case_id: str, version_number: int
    ) -> InvoiceCaseVersion | None:
        """Read an exact immutable snapshot with mandatory tenant scope.

        Args:
            tenant_id: Permitted tenant.
            case_id: Stable case identifier.
            version_number: Exact snapshot number.

        Returns:
            The snapshot, or None outside that tenant or when absent.
        """
        tenant_id = _validated(_Identifier, tenant_id)
        case_id = _validated(_Identifier, case_id)
        version_number = _validated(_Version, version_number)
        result = await self._db.execute(
            self._version_query().where(
                InvoiceCaseVersionRow.tenant_id == tenant_id,
                InvoiceCaseVersionRow.case_id == case_id,
                InvoiceCaseVersionRow.version_number == version_number,
            )
        )
        row = result.first()
        return self._from_row(row) if row is not None else None

    async def list_versions(
        self, *, tenant_id: str, case_id: str, limit: int = 100, offset: int = 0
    ) -> tuple[InvoiceCaseVersion, ...]:
        """Read tenant-owned case history in descending revision order.

        Args:
            tenant_id: Permitted tenant.
            case_id: Stable case identifier.
            limit: Page size, at most 100.
            offset: Number of snapshots to skip.

        Returns:
            Snapshots with their separately persisted AP decisions.
        """
        tenant_id = _validated(_Identifier, tenant_id)
        case_id = _validated(_Identifier, case_id)
        limit = _validated(_Limit, limit)
        offset = _validated(_Offset, offset)
        result = await self._db.execute(
            self._version_query()
            .where(
                InvoiceCaseVersionRow.tenant_id == tenant_id,
                InvoiceCaseVersionRow.case_id == case_id,
            )
            .order_by(InvoiceCaseVersionRow.version_number.desc())
            .limit(limit)
            .offset(offset)
        )
        return tuple(self._from_row(row) for row in result.all())

    async def list_latest(
        self, *, tenant_id: str, limit: int = 100, offset: int = 0
    ) -> tuple[InvoiceCaseVersion, ...]:
        """List one latest snapshot per case, newest created case first.

        Args:
            tenant_id: Permitted tenant.
            limit: Page size, at most 100.
            offset: Number of cases to skip.

        Returns:
            Latest case snapshots ordered by creation time and identifier.
        """
        tenant_id = _validated(_Identifier, tenant_id)
        limit = _validated(_Limit, limit)
        offset = _validated(_Offset, offset)
        result = await self._db.execute(
            self._version_query()
            .where(
                InvoiceCase.tenant_id == tenant_id,
                InvoiceCase.latest_version == InvoiceCaseVersionRow.version_number,
            )
            .order_by(InvoiceCase.created_at.desc(), InvoiceCase.id.desc())
            .limit(limit)
            .offset(offset)
        )
        return tuple(self._from_row(row) for row in result.all())

    async def duplicate_owner(self, *, tenant_id: str, duplicate_key: str) -> str | None:
        """Read the retained tenant-owned claim for a SHA-256 business key.

        Args:
            tenant_id: Permitted tenant.
            duplicate_key: Lowercase SHA-256 business key.

        Returns:
            Owning case identifier, or None when unclaimed in the tenant.
        """
        tenant_id = _validated(_Identifier, tenant_id)
        duplicate_key = _validated(_Digest, duplicate_key)
        result = await self._db.execute(
            select(InvoiceDuplicateClaim.case_id).where(
                InvoiceDuplicateClaim.tenant_id == tenant_id,
                InvoiceDuplicateClaim.duplicate_key == duplicate_key,
            )
        )
        return result.scalar_one_or_none()

    async def lock_for_decision(
        self,
        *,
        case_id: str,
        expected_version: int,
        actor: AgreementActor,
        agreement_id: str | None,
    ) -> None:
        """Hold case and optional agreement locks for host reference revalidation.

        Args:
            case_id: Case the reviewer is deciding.
            expected_version: Exact latest reviewed revision.
            actor: Authorized reviewer and tenant scope.
            agreement_id: Same-tenant referenced agreement, if available.

        Raises:
            AgreementMasterError: Unauthorized, stale, replayed, or missing reference.
        """
        case_id = _validated(_Identifier, case_id)
        expected_version = _validated(_Version, expected_version)
        actor = _validated_model(AgreementActor, actor)
        agreement_id = _validated(_Identifier, agreement_id) if agreement_id is not None else None
        self._require_authority(actor)
        # Releasing a savepoint retains PostgreSQL row locks until the host ends
        # its outer transaction. Both append and decide share this header CAS.
        async with self._db.begin_nested():
            await self._guard_revision(actor.tenant_id, case_id, expected_version, increment=False)
            await self._undecided_row(actor.tenant_id, case_id, expected_version)
            if agreement_id is not None:
                result = cast(
                    CursorResult[Any],
                    await self._db.execute(
                        update(Agreement)
                        .where(Agreement.tenant_id == actor.tenant_id, Agreement.id == agreement_id)
                        .values(latest_version=Agreement.latest_version)
                        .execution_options(synchronize_session=False)
                    ),
                )
                if result.rowcount != 1:
                    raise AgreementMasterError("conflict", "Agreement reference is unavailable")

    async def decide(
        self, *, case_id: str, expected_version: int, decision: APDecision, actor: AgreementActor
    ) -> InvoiceCaseVersion:
        """Record one immutable authorized AP decision on the latest case version.

        Args:
            case_id: Stable case identifier.
            expected_version: Exact latest reviewed revision.
            decision: Explicit approval or rejection with review reason.
            actor: Authorized reviewer and tenant scope.

        Returns:
            The case snapshot with its immutable decision.

        Raises:
            AgreementMasterError: Unauthorized, stale, replayed, or duplicate approval.
        """
        case_id = _validated(_Identifier, case_id)
        expected_version = _validated(_Version, expected_version)
        decision = _validated_model(APDecision, decision)
        actor = _validated_model(AgreementActor, actor)
        self._require_authority(actor)
        record = InvoiceCaseDecision(
            tenant_id=actor.tenant_id,
            case_id=case_id,
            version_number=expected_version,
            decision=decision.model_dump(mode="json"),
            decided_by=actor.user_id,
            decided_at=datetime.now(timezone.utc),
        )
        try:
            async with self._db.begin_nested():
                await self._guard_revision(
                    actor.tenant_id, case_id, expected_version, increment=False
                )
                row = await self._undecided_row(actor.tenant_id, case_id, expected_version)
                header, snapshot, _ = row
                if decision.action == "approve" and snapshot.duplicate_of is not None:
                    raise AgreementMasterError(
                        "conflict", "Duplicate invoice cases cannot be approved"
                    )
                self._db.add(record)
                await self._db.flush()
        except IntegrityError:
            raise AgreementMasterError("conflict", "Invoice case decision already exists") from None
        return self._materialize(header, snapshot, record)

    async def _reserve_installment(
        self,
        package: InvoicePackage,
        assessment: ReconciliationAssessment,
        tenant_id: str,
        case_id: str,
    ) -> str | None:
        if assessment.agreement_reference is None or assessment.outcome not in (
            "matched",
            "needs_review",
        ):
            return None
        return await self._reserve_duplicate(tenant_id, installment_duplicate_key(package), case_id)

    async def _reserve_duplicate(
        self, tenant_id: str, duplicate_key: str | None, case_id: str
    ) -> str | None:
        if duplicate_key is None:
            return None
        owner = await self.duplicate_owner(tenant_id=tenant_id, duplicate_key=duplicate_key)
        if owner is None:
            try:
                async with self._db.begin_nested():
                    self._db.add(
                        InvoiceDuplicateClaim(
                            tenant_id=tenant_id, duplicate_key=duplicate_key, case_id=case_id
                        )
                    )
                    await self._db.flush()
                owner = case_id
            except IntegrityError:
                # The unique tenant/key claim serializes concurrent contenders.
                # PostgreSQL READ COMMITTED observes the committed winner here.
                owner = await self.duplicate_owner(tenant_id=tenant_id, duplicate_key=duplicate_key)
                if owner is None:
                    raise AgreementMasterError(
                        "conflict", "Invoice duplicate claim could not be reserved"
                    ) from None
        return owner if owner != case_id else None

    async def _guard_revision(
        self, tenant_id: str, case_id: str, expected_version: int, *, increment: bool
    ) -> None:
        result = cast(
            CursorResult[Any],
            await self._db.execute(
                update(InvoiceCase)
                .where(
                    InvoiceCase.tenant_id == tenant_id,
                    InvoiceCase.id == case_id,
                    InvoiceCase.latest_version == expected_version,
                )
                .values(latest_version=expected_version + 1 if increment else expected_version)
                .execution_options(synchronize_session=False)
            ),
        )
        if result.rowcount != 1:
            raise AgreementMasterError("conflict", "Invoice case revision is stale or unavailable")

    async def _header(self, tenant_id: str, case_id: str) -> InvoiceCase | None:
        result = await self._db.execute(
            select(InvoiceCase)
            .where(InvoiceCase.tenant_id == tenant_id, InvoiceCase.id == case_id)
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    async def _undecided_row(self, tenant_id: str, case_id: str, version_number: int) -> Row[Any]:
        result = await self._db.execute(
            self._version_query()
            .where(
                InvoiceCaseVersionRow.tenant_id == tenant_id,
                InvoiceCaseVersionRow.case_id == case_id,
                InvoiceCaseVersionRow.version_number == version_number,
            )
            .limit(1)
        )
        row = result.first()
        if row is None or row[2] is not None:
            raise AgreementMasterError(
                "conflict", "Invoice case revision is unavailable or already decided"
            )
        return row

    @staticmethod
    def _require_authority(actor: AgreementActor) -> None:
        if not actor.can_approve:
            raise AgreementMasterError("forbidden", "AP decision permission is required")

    @staticmethod
    def _identity(header: InvoiceCase) -> AgreementIdentity:
        return AgreementIdentity(
            vendor_id=header.vendor_id,
            store_id=header.store_id,
            contract_number=header.contract_number,
        )

    @staticmethod
    def _snapshot(
        case_id: str,
        version_number: int,
        package: InvoicePackage,
        assessment: ReconciliationAssessment,
        duplicate_of: str | None,
        actor: AgreementActor,
    ) -> InvoiceCaseVersionRow:
        return InvoiceCaseVersionRow(
            tenant_id=actor.tenant_id,
            case_id=case_id,
            version_number=version_number,
            package=package.model_dump(mode="json"),
            assessment=assessment.model_dump(mode="json"),
            duplicate_of=duplicate_of,
            created_by=actor.user_id,
            created_at=datetime.now(timezone.utc),
        )

    @staticmethod
    def _version_query() -> Select[tuple[InvoiceCase, InvoiceCaseVersionRow, InvoiceCaseDecision]]:
        return (
            select(InvoiceCase, InvoiceCaseVersionRow, InvoiceCaseDecision)
            .join(
                InvoiceCaseVersionRow,
                and_(
                    InvoiceCase.tenant_id == InvoiceCaseVersionRow.tenant_id,
                    InvoiceCase.id == InvoiceCaseVersionRow.case_id,
                ),
            )
            .outerjoin(
                InvoiceCaseDecision,
                and_(
                    InvoiceCaseVersionRow.tenant_id == InvoiceCaseDecision.tenant_id,
                    InvoiceCaseVersionRow.case_id == InvoiceCaseDecision.case_id,
                    InvoiceCaseVersionRow.version_number == InvoiceCaseDecision.version_number,
                ),
            )
        )

    @classmethod
    def _from_row(cls, row: Row[Any]) -> InvoiceCaseVersion:
        header, snapshot, decision = row
        return cls._materialize(header, snapshot, decision)

    @staticmethod
    def _materialize(
        header: InvoiceCase, snapshot: InvoiceCaseVersionRow, decision: InvoiceCaseDecision | None
    ) -> InvoiceCaseVersion:
        record = (
            APDecisionRecord(
                **decision.decision,
                decided_by=decision.decided_by,
                decided_at=_aware(decision.decided_at),
            )
            if decision is not None
            else None
        )
        return InvoiceCaseVersion(
            case_id=header.id,
            tenant_id=header.tenant_id,
            version_number=snapshot.version_number,
            package=InvoicePackage.model_validate(snapshot.package),
            assessment=ReconciliationAssessment.model_validate(snapshot.assessment),
            duplicate_of=snapshot.duplicate_of,
            created_by=snapshot.created_by,
            created_at=_aware(snapshot.created_at),
            decision=record,
        )
