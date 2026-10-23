"""Async storage boundary for tenant-scoped policy revisions."""

from abc import ABC, abstractmethod

from src.paper.contracts import AgreementActor

from .request import UpdateFieldPolicyRequest
from .version import FieldPolicyVersion


class BaseFieldPolicyRepository(ABC):
    """Read current policy and atomically append immutable revisions."""

    @abstractmethod
    async def get_latest(self, *, tenant_id: str) -> FieldPolicyVersion | None:
        """Read only the tenant's current revision in the host transaction."""

    @abstractmethod
    async def append(
        self, *, actor: AgreementActor, request: UpdateFieldPolicyRequest
    ) -> FieldPolicyVersion:
        """Compare-and-swap the revision and stamp trusted audit provenance."""
