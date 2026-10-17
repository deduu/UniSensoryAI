"""Persistence boundary for agreement master operations."""

from abc import ABC, abstractmethod

from src.paper.contracts import (
    AgreementActor,
    AgreementDraft,
    AgreementIdentity,
    AgreementLookup,
    AgreementVersion,
    ApprovalDecision,
)


class BaseAgreementRepository(ABC):
    """Async, tenant-scoped storage with atomic version and approval guards.

    Adapters flush changes within a host-owned transaction. Append and approval
    must serialize mutations for an agreement and reject stale version claims.
    Snapshots and approval decisions cannot be overwritten through this port.
    Persist independent snapshots so changes to caller-owned collections cannot
    modify stored history. The host owns transaction commit and rollback.
    """

    @abstractmethod
    async def create(
        self, *, identity: AgreementIdentity, draft: AgreementDraft, actor: AgreementActor
    ) -> AgreementVersion:
        """Insert a unique agreement and its first draft snapshot.

        Args:
            identity: Stable vendor, store, and contract identifiers.
            draft: Source terms and provenance to snapshot independently.
            actor: Trusted author and tenant established by the host.

        Returns:
            Version one within the host-owned transaction.
        """
        raise NotImplementedError

    @abstractmethod
    async def append(
        self,
        *,
        agreement_id: str,
        draft: AgreementDraft,
        expected_version: int,
        actor: AgreementActor,
    ) -> AgreementVersion:
        """Append a snapshot with an atomic expected-latest-version guard.

        Args:
            agreement_id: Existing agreement identifier in the actor's tenant.
            draft: New content and change reason; prior content is retained.
            expected_version: Latest revision previously read by the author.
            actor: Trusted author and tenant established by the host.

        Returns:
            The next draft version, rejecting stale revision claims.
        """
        raise NotImplementedError

    @abstractmethod
    async def approve(
        self,
        *,
        agreement_id: str,
        version_number: int,
        decision: ApprovalDecision,
        actor: AgreementActor,
    ) -> AgreementVersion:
        """Publish the latest version once, recording the authorized actor.

        Args:
            agreement_id: Existing agreement identifier in the actor's tenant.
            version_number: Exact reviewed version, which must remain latest.
            decision: Validated reviewer decision, separate from extracted terms.
            actor: Trusted approver and tenant established by the host.

        Returns:
            The version with a separate immutable approval record.
        """
        raise NotImplementedError

    @abstractmethod
    async def get_version(
        self, *, tenant_id: str, agreement_id: str, version_number: int
    ) -> AgreementVersion | None:
        """Read one version only within the supplied tenant.

        Args:
            tenant_id: Trusted tenant scope supplied by the host.
            agreement_id: Agreement identifier to read.
            version_number: Exact historical revision.

        Returns:
            Independent version data, or None if absent in this tenant.
        """
        raise NotImplementedError

    @abstractmethod
    async def list_versions(
        self, *, tenant_id: str, agreement_id: str, limit: int = 100, offset: int = 0
    ) -> tuple[AgreementVersion, ...]:
        """Read version history newest first within the supplied tenant.

        Args:
            tenant_id: Trusted tenant scope supplied by the host.
            agreement_id: Agreement identifier to read.
            limit: Maximum page size, between one and 100.
            offset: Nonnegative number of versions to skip.

        Returns:
            Independent version snapshots in descending revision order.
        """
        raise NotImplementedError

    async def list_latest(
        self, *, tenant_id: str, limit: int = 100, offset: int = 0
    ) -> tuple[AgreementVersion, ...]:
        """Read a queue of latest agreement snapshots in stable descending order.

        This optional read capability preserves existing lifecycle-only adapters.
        Adapters supporting agreement queues must implement it explicitly.

        Args:
            tenant_id: Trusted tenant scope supplied by the host.
            limit: Maximum page size, between one and 100.
            offset: Nonnegative number of agreements to skip.

        Returns:
            One latest snapshot per agreement, most recently revised first.

        Raises:
            NotImplementedError: The adapter does not provide agreement queues.
        """
        raise NotImplementedError("Agreement queue reads are not supported by this adapter.")

    @abstractmethod
    async def find_approved(
        self, *, tenant_id: str, lookup: AgreementLookup
    ) -> AgreementVersion | None:
        """Read the latest started approval without reviving expired terms.

        Args:
            tenant_id: Trusted tenant scope supplied by the host.
            lookup: Exact canonical identity and effective business date.

        Returns:
            The highest approved revision whose start has occurred, if its end
            date is inclusive of the lookup date; otherwise None. Newer drafts
            and future approvals do not hide earlier applicable approvals.
        """
        raise NotImplementedError
