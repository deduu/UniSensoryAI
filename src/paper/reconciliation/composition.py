"""Async loading of host-owned reconciliation requirements."""

import asyncio
from pathlib import Path

import yaml
from pydantic import ValidationError

from src.paper.errors import AgreementMasterError

from .engine import ReconciliationEngine
from .installment_rule import InstallmentReconciliationRule
from .ports.rule import BaseReconciliationRule
from .settings import ReconciliationSettings
from .withholding_rule import WithholdingReconciliationRule


def build_reconciliation_engine(
    settings: ReconciliationSettings,
    extra_rules: tuple[BaseReconciliationRule, ...] = (),
) -> ReconciliationEngine:
    """Inject explicitly enabled, versioned rules without choosing any model.

    Args:
        settings: Validated host-owned requirements and enabled capabilities.
        extra_rules: Additional host rules implementing the existing rule port.

    Returns:
        A deterministic engine whose policy fingerprint includes every rule.
    """
    settings = ReconciliationSettings.model_validate(settings)
    rules: list[BaseReconciliationRule] = []
    for name in settings.enabled_rules:
        rules.append(
            InstallmentReconciliationRule()
            if name == "installments"
            else WithholdingReconciliationRule()
        )
    return ReconciliationEngine(settings, extra_rules=(*rules, *extra_rules))


def _read_settings(path: Path) -> ReconciliationSettings:
    with path.open(encoding="utf-8") as source:
        return ReconciliationSettings.model_validate(yaml.safe_load(source))


async def load_reconciliation_settings(config_path: Path | None = None) -> ReconciliationSettings:
    """Read a deployment-owned YAML policy outside the event loop.

    Args:
        config_path: Host configuration path, or the packaged default policy.

    Returns:
        Validated requirements, AP reviewer roles, and repository deadlines.
    """
    try:
        return await asyncio.to_thread(
            _read_settings, config_path or Path(__file__).with_name("defaults.yaml")
        )
    except (OSError, ValidationError, yaml.YAMLError):
        raise AgreementMasterError(
            "invalid_configuration", "Reconciliation policy configuration is invalid."
        ) from None
