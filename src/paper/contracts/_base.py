"""Validated immutable agreement contract primitives."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints, model_validator

Identifier = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)]
Reason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)]


class _Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, revalidate_instances="always")

    @model_validator(mode="before")
    @classmethod
    def _restore_output(cls, value: object) -> object:
        if isinstance(value, dict):
            return {
                key: item for key, item in value.items() if key not in cls.model_computed_fields
            }
        return value
