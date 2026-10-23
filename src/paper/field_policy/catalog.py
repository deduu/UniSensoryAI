"""Public effective field policy without deployment paths or authorization lists."""

from pydantic import AwareDatetime, Field

from src.paper.contracts._base import Identifier, _Contract
from src.paper.readiness.requirement import FieldRequirement


class FieldPolicyCatalog(_Contract):
    """All supported effective field requirements and trusted editing capability."""

    revision: int = Field(ge=0, le=2147483647, strict=True)
    policy_id: Identifier
    policy_version: Identifier
    can_edit: bool
    requirements: tuple[FieldRequirement, ...] = Field(max_length=128)
    base_requirements: tuple[FieldRequirement, ...] = Field(max_length=128)
    overrides: tuple[FieldRequirement, ...] = Field(max_length=128)
    updated_by: Identifier | None = None
    updated_at: AwareDatetime | None = None
