"""Bounded edits to document matching presence requirements."""

from pydantic import Field, model_validator

from src.paper.contracts._base import _Contract
from src.paper.readiness.requirement import FieldRequirement


class UpdateFieldPolicyRequest(_Contract):
    """Replace explicit tenant overrides using an optimistic revision guard.

    Inherited catalog rows are guidance, not overrides. An empty tuple removes
    all tenant overrides while retaining deployment-owned requirements.
    """

    expected_revision: int = Field(ge=0, le=2147483646, strict=True)
    requirements: tuple[FieldRequirement, ...] = Field(max_length=128)

    @model_validator(mode="after")
    def _unique_fields(self) -> "UpdateFieldPolicyRequest":
        keys = {(item.role, item.field) for item in self.requirements}
        if len(keys) != len(self.requirements):
            raise ValueError("A document field may have only one requirement.")
        return self
