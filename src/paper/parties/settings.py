"""Host-owned role lexicon, independent of inference providers and sample data."""

import asyncio
from pathlib import Path

import yaml
from pydantic import Field, ValidationError, model_validator

from src.extraction.contracts.base import _Contract

from .normalization import normalized_text


class PartyRoleSettings(_Contract):
    """Explicit role labels; first/second party order never establishes a role."""

    policy_id: str = Field(default="paper.party_roles", min_length=1, max_length=128)
    policy_version: str = Field(default="1", min_length=1, max_length=64)
    landlord_labels: tuple[str, ...] = Field(
        default=("YANG MENYEWAKAN", "LESSOR", "LANDLORD"), min_length=1, max_length=128
    )
    tenant_labels: tuple[str, ...] = Field(
        default=("PENYEWA", "LESSEE", "TENANT"), min_length=1, max_length=128
    )

    @model_validator(mode="after")
    def validate_lexicon(self) -> "PartyRoleSettings":
        """Reject ambiguous, duplicate, empty or unbounded role labels."""
        normalized = [
            tuple(normalized_text(label) for label in labels)
            for labels in (self.landlord_labels, self.tenant_labels)
        ]
        if any(not all(labels) or len(set(labels)) != len(labels) for labels in normalized) or (
            set(normalized[0]) & set(normalized[1])
        ):
            raise ValueError("Party role labels must be nonempty and unambiguous.")
        if any(len(label) > 256 for label in (*self.landlord_labels, *self.tenant_labels)):
            raise ValueError("Party role labels exceed their supported limit.")
        return self


def _read_settings(path: Path) -> PartyRoleSettings:
    with path.open(encoding="utf-8") as source:
        return PartyRoleSettings.model_validate(yaml.safe_load(source))


async def load_party_role_settings(config_path: Path | None = None) -> PartyRoleSettings:
    """Load validated deployment YAML without blocking the event loop.

    Args:
        config_path: Optional host policy path; otherwise packaged defaults.

    Returns:
        Validated role labels without document-specific names or model settings.

    Raises:
        ValueError: Configuration cannot be read or validated, with no source values.
    """
    try:
        return await asyncio.to_thread(
            _read_settings, config_path or Path(__file__).with_name("defaults.yaml")
        )
    except (OSError, UnicodeError, ValidationError, yaml.YAMLError):
        raise ValueError("Party role configuration is invalid.") from None
