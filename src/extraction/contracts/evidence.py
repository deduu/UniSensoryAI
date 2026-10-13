"""Field evidence stays outside the external business payload."""

from pydantic import Field, field_validator

from .base import _Contract


class FieldEvidence(_Contract):
    """Source block identifiers and a literal quote supporting a JSON field path."""

    field_path: str = Field(pattern=r"^/")
    source_ids: tuple[str, ...] = Field(min_length=1)
    quote: str = Field(min_length=1)

    @field_validator("quote")
    @classmethod
    def nonempty_quote(cls, value: str) -> str:
        """Reject whitespace that cannot establish source evidence."""
        if not value.strip():
            raise ValueError("Evidence requires a nonempty literal quote.")
        return value
