"""Pure host rule extension port, independent from models and transport."""

from abc import ABC, abstractmethod

from src.paper.contracts import AgreementVersion

from ..contracts import InvoicePackage, ReconciliationFinding
from ..settings import ReconciliationSettings


class BaseReconciliationRule(ABC):
    """A deterministic, synchronous business rule with explicit host versioning.

    Implementations must perform no I/O and must not return source document
    values in diagnostic messages. Each rule returns at most 100 findings.
    Blocking missing-data rules use codes starting
    with ``missing_``; other blocking rules describe mismatches. Rule version
    changes must accompany behavioral changes so stored policy hashes invalidate.
    """

    @property
    @abstractmethod
    def rule_id(self) -> str:
        """Return a stable host-owned rule identifier."""

    @property
    @abstractmethod
    def rule_version(self) -> str:
        """Return the version whose behavior is bound to the assessment."""

    @abstractmethod
    def evaluate(
        self,
        package: InvoicePackage,
        *,
        agreement: AgreementVersion | None,
        settings: ReconciliationSettings,
    ) -> tuple[ReconciliationFinding, ...]:
        """Return source-qualified findings against already scoped authority."""
