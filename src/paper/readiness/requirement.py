"""External-system field requirements owned by versioned host policy."""

from typing import Literal

from pydantic import model_validator

from src.paper.contracts._base import Identifier, Reason, _Contract

from ._schemas import DocumentRole, scalar_fields
from .condition import FieldCondition


class FieldRequirement(_Contract):
    """Describe required, conditional, or optional presence of a canonical field."""

    role: DocumentRole
    field: Identifier
    requirement: Literal["required", "conditional", "optional"]
    reason: Reason
    when: FieldCondition | None = None

    @model_validator(mode="after")
    def _valid_requirement(self) -> "FieldRequirement":
        if self.field not in scalar_fields(self.role):
            raise ValueError("Requirements reference an unsupported scalar field.")
        if (self.requirement == "conditional") != (self.when is not None):
            raise ValueError("Only conditional requirements must carry a condition.")
        return self
