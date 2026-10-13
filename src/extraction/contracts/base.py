"""Shared immutable contract configuration."""

from pydantic import BaseModel, ConfigDict, model_validator


class _Contract(BaseModel):
    model_config = ConfigDict(
        extra="forbid", frozen=True, revalidate_instances="always", allow_inf_nan=False
    )

    @model_validator(mode="before")
    @classmethod
    def _restore_serialized_output(cls, value: object) -> object:
        if isinstance(value, dict):
            return {
                key: item for key, item in value.items() if key not in cls.model_computed_fields
            }
        return value
