"""Atomic persistence boundary for manually supplied PAPER invoice cases."""

from abc import ABC, abstractmethod

from src.paper.contracts import AgreementActor
from src.paper.reconciliation.contracts import (
    APDecision,
    InvoiceCaseVersion,
    InvoicePackage,
    ReconciliationAssessment,
)


class BaseInvoiceCaseRepository(ABC):
    """Persist independent tenant-scoped snapshots in a host-owned transaction.

    Append, decision locking, and decisions serialize on the same case header.
    Duplicate claims are atomic and tenant-scoped; a losing claim still creates
    a durable case referencing its original owner. Claims remain reserved across
    corrections and rejections. Stored content and decisions cannot be edited.
    For a package naming an installment, create/append must also reserve
    installment_duplicate_key(package) when its assessment has an approved
    reference and outcome matched or needs_review, provided the invoice-number
    claim was not lost. Reserve both claims in the same transaction, using this
    same claim namespace and duplicate_owner lookup. This prevents another invoice
    or agreement revision from claiming that stable obligation. Approval checks
    retained ownership; adapters without this capability fail closed.
    The host commits or rolls back; it must share the transaction with agreement
    reads when publishing an AP approval.
    """

    @abstractmethod
    async def create(
        self,
        *,
        package: InvoicePackage,
        assessment: ReconciliationAssessment,
        duplicate_key: str | None,
        actor: AgreementActor,
    ) -> InvoiceCaseVersion:
        """Persist an initial assessment and atomically reserve its duplicate key.

        Args:
            package: Validated document roles and source-derived fields.
            assessment: Deterministic findings and pinned agreement/policy reference.
            duplicate_key: Server-derived business fingerprint, if available.
            actor: Trusted tenant and author identity.

        Returns:
            Version one, including any same-tenant duplicate owner.
        """
        raise NotImplementedError

    @abstractmethod
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
        """Append a fresh assessment while preserving canonical case identity.

        Args:
            case_id: Case identifier in the actor's tenant.
            package: Corrected or supplemented source package.
            assessment: New findings and current reference/policy pin.
            duplicate_key: Server-derived business fingerprint, if available.
            expected_version: Latest revision previously read by the author.
            actor: Trusted tenant and author identity.

        Returns:
            The next undecided case version, rejecting stale revision claims.
        """
        raise NotImplementedError

    @abstractmethod
    async def get_version(
        self,
        *,
        tenant_id: str,
        case_id: str,
        version_number: int,
    ) -> InvoiceCaseVersion | None:
        """Read an exact historical version only within the supplied tenant.

        Args:
            tenant_id: Trusted tenant scope.
            case_id: Case identifier to read.
            version_number: Exact case revision.

        Returns:
            Independent version data, or None if absent in this tenant.
        """
        raise NotImplementedError

    @abstractmethod
    async def list_versions(
        self,
        *,
        tenant_id: str,
        case_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[InvoiceCaseVersion, ...]:
        """Read case history newest first within the supplied tenant.

        Args:
            tenant_id: Trusted tenant scope.
            case_id: Case identifier to read.
            limit: Page size between one and 100.
            offset: Nonnegative number of versions to skip.

        Returns:
            Independent version snapshots in descending revision order.
        """
        raise NotImplementedError

    @abstractmethod
    async def list_latest(
        self,
        *,
        tenant_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[InvoiceCaseVersion, ...]:
        """Read current versions of cases, newest created case first.

        Args:
            tenant_id: Trusted tenant scope.
            limit: Page size between one and 100.
            offset: Nonnegative number of cases to skip.

        Returns:
            One latest version per case in this tenant.
        """
        raise NotImplementedError

    @abstractmethod
    async def duplicate_owner(self, *, tenant_id: str, duplicate_key: str) -> str | None:
        """Read a business duplicate claim within the supplied tenant.

        Args:
            tenant_id: Trusted tenant scope.
            duplicate_key: Server-derived fingerprint.

        Returns:
            Owning case identifier, or None if unclaimed.
        """
        raise NotImplementedError

    @abstractmethod
    async def lock_for_decision(
        self,
        *,
        case_id: str,
        expected_version: int,
        actor: AgreementActor,
        agreement_id: str | None,
    ) -> None:
        """Hold case and optional agreement authority until host transaction ends.

        Args:
            case_id: Case identifier in the actor's tenant.
            expected_version: Exact latest case revision reviewed by AP.
            actor: Trusted tenant and AP identity.
            agreement_id: Pinned agreement to lock before current reference reads.

        Raises:
            AgreementMasterError: Stale, decided, missing, or unauthorized case.
        """
        raise NotImplementedError

    @abstractmethod
    async def decide(
        self,
        *,
        case_id: str,
        expected_version: int,
        decision: APDecision,
        actor: AgreementActor,
    ) -> InvoiceCaseVersion:
        """Append an immutable AP record to the exact latest version once.

        Args:
            case_id: Case identifier in the actor's tenant.
            expected_version: Revision locked and revalidated by the workflow.
            decision: Explicit disposition, reason, and allowed exception overrides.
            actor: Trusted tenant and AP authority.

        Returns:
            The stored case version with reviewer identity and UTC decision time.
        """
        raise NotImplementedError
