"""A declarative, bounded field predicate without executable expressions."""

from typing import Annotated, Literal

from pydantic import (
    ConfigDict,
    StrictBool,
    StrictFloat,
    StrictInt,
    StringConstraints,
    model_validator,
)

from src.paper.contracts._base import Identifier, _Contract

from ._schemas import DocumentRole, scalar_fields, validate_scalar


class FieldCondition(_Contract):
    """Activate a requirement from one typed source field in selected documents."""

    model_config = ConfigDict(
        extra="forbid", frozen=True, revalidate_instances="always", allow_inf_nan=False
    )
    role: DocumentRole
    field: Identifier
    operator: Literal["present", "absent", "equals"]
    value: (
        Annotated[str, StringConstraints(strict=True, max_length=4000)]
        | StrictInt
        | StrictFloat
        | StrictBool
        | None
    ) = None

    @model_validator(mode="after")
    def _valid_predicate(self) -> "FieldCondition":
        if self.field not in scalar_fields(self.role):
            raise ValueError("Field conditions reference an unsupported scalar field.")
        if self.operator == "equals":
            if "value" not in self.model_fields_set or self.value is None:
                raise ValueError("Equality conditions require a non-null typed scalar value.")
            normalized = validate_scalar(self.role, self.field, self.value)
            object.__setattr__(self, "value", normalized)
        elif "value" in self.model_fields_set and self.value is not None:
            raise ValueError("Presence conditions must not carry an equality value.")
        return self
