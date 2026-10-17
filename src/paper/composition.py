"""Async host configuration without database or model construction."""

import asyncio
from pathlib import Path

import yaml
from pydantic import ValidationError

from src.paper.errors import AgreementMasterError
from src.paper.settings import AgreementMasterSettings


def _read_settings(path: Path) -> AgreementMasterSettings:
    with path.open(encoding="utf-8") as source:
        return AgreementMasterSettings.model_validate(yaml.safe_load(source))


async def load_agreement_settings(config_path: Path | None = None) -> AgreementMasterSettings:
    """Read a host-selected policy file away from the event loop.

    Args:
        config_path: Deployment-owned YAML path; defaults to packaged policy.

    Returns:
        Validated approval, authorization, and storage deadline settings.
    """
    try:
        return await asyncio.to_thread(
            _read_settings, config_path or Path(__file__).with_name("defaults.yaml")
        )
    except (OSError, ValidationError, yaml.YAMLError):
        raise AgreementMasterError(
            "invalid_configuration", "Agreement policy configuration is invalid."
        ) from None
