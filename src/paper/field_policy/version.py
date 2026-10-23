"""Immutable storage contract for a tenant's requirement revision."""

from pydantic import AwareDatetime, Field, model_validator

from src.paper.contracts._base import Identifier, _Contract
from src.paper.field_policy.request import UpdateFieldPolicyRequest
from src.paper.readiness.requirement import FieldRequirement


class FieldPolicyVersion(_Contract):
    """Server-attested requirements, author and update time."""

    tenant_id: Identifier
    revision: int = Field(ge=1, le=2147483647, strict=True)
    requirements: tuple[FieldRequirement, ...] = Field(max_length=128)
    updated_by: Identifier
    updated_at: AwareDatetime

    @model_validator(mode="after")
    def _valid_requirements(self) -> "FieldPolicyVersion":
        UpdateFieldPolicyRequest(expected_revision=0, requirements=self.requirements)
        return self
