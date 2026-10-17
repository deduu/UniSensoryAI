"""Historical agreement content and its optional publication decision."""

from typing import Literal

from pydantic import AwareDatetime, PositiveInt, computed_field

from ._base import Identifier, _Contract
from .approval_record import ApprovalRecord
from .draft import AgreementDraft
from .identity import AgreementIdentity


class AgreementVersion(_Contract):
    """A snapshot; subsequent corrections create another version."""

    agreement_id: Identifier
    tenant_id: Identifier
    version_number: PositiveInt
    identity: AgreementIdentity
    draft: AgreementDraft
    created_by: Identifier
    created_at: AwareDatetime
    approval: ApprovalRecord | None = None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def status(self) -> Literal["draft", "approved"]:
        """Only an explicit approval makes this version authoritative."""
        return "approved" if self.approval is not None else "draft"
