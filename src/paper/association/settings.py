"""Host-owned ranking policy and bounded repository reads."""

import asyncio
from pathlib import Path

import yaml
from pydantic import Field, ValidationError

from src.paper.contracts._base import Identifier, _Contract
from src.paper.errors import AgreementMasterError


class AssociationSettings(_Contract):
    """Deterministic ranking weights are configuration, never model confidence."""

    policy_id: Identifier = "paper.contract_association"
    policy_version: Identifier = "1"
    contract_weight: int = Field(default=100, ge=0, le=10000)
    identity_weight: int = Field(default=60, ge=0, le=10000)
    supplier_weight: int = Field(default=20, ge=0, le=10000)
    location_weight: int = Field(default=20, ge=0, le=10000)
    history_page_limit: int = Field(default=100, ge=1, le=100)
    max_history_pages: int = Field(default=10, ge=1, le=100)
    timeout_seconds: float = Field(default=15.0, gt=0, le=15)


def _read_settings(path: Path) -> AssociationSettings:
    with path.open(encoding="utf-8") as source:
        return AssociationSettings.model_validate(yaml.safe_load(source))


async def load_association_settings(config_path: Path | None = None) -> AssociationSettings:
    """Read deployment-owned policy off the event loop.

    Args:
        config_path: Optional deployment-owned YAML file.

    Returns:
        Validated model-independent candidate policy.
    """
    try:
        return await asyncio.to_thread(
            _read_settings, config_path or Path(__file__).with_name("defaults.yaml")
        )
    except (OSError, ValidationError, yaml.YAMLError):
        raise AgreementMasterError(
            "invalid_configuration", "Contract association policy is invalid."
        ) from None
