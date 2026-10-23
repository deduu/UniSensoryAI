"""Build an extraction runtime without application startup or ML imports."""

import asyncio
import os
import re
from collections.abc import Callable, Mapping
from pathlib import Path

import yaml
from pydantic import Field

from .capabilities import DocumentExtractionInput, FieldExtractionInput
from .contracts import DocumentResult, FieldExtractionResult, ModelDescriptor
from .contracts.base import _Contract
from .errors import ExtractionError
from .model_gateway import ModelGateway
from .pdf_reader import PdfReader
from .ports import BaseCapability, BaseGenerationProvider, BasePdfReader
from .provider_profile import ProviderProfile
from .providers import OpenAICompatibleGenerationProvider
from .service import ExtractionService
from .settings import ExtractionSettings

ProviderFactory = Callable[[ProviderProfile], BaseGenerationProvider]
_ENVIRONMENT_REFERENCE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


class _RuntimeConfig(_Contract):
    settings: ExtractionSettings = Field(default_factory=ExtractionSettings)
    profiles: dict[str, ProviderProfile] = Field(default_factory=dict)


def _resolve_environment(value: object) -> object:
    if isinstance(value, str):

        def replacement(match: re.Match[str]) -> str:
            configured = os.getenv(match.group(1))
            if not configured:
                raise ValueError("A configuration environment variable is missing.")
            return configured

        # Substitute once: environment values are data, never further templates.
        return _ENVIRONMENT_REFERENCE.sub(replacement, value)
    if isinstance(value, dict):
        return {key: _resolve_environment(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_resolve_environment(item) for item in value]
    return value


def _read_config(path: Path) -> _RuntimeConfig:
    try:
        with path.open(encoding="utf-8") as stream:
            payload = yaml.safe_load(stream)
        return _RuntimeConfig.model_validate(_resolve_environment(payload or {}))
    except (OSError, yaml.YAMLError, ValueError):
        raise ExtractionError(
            "invalid_configuration", "Extraction configuration is invalid or unavailable."
        ) from None


def _openai_factory(profile: ProviderProfile) -> BaseGenerationProvider:
    if profile.base_url is None:
        raise ExtractionError(
            "invalid_configuration", "The generation endpoint must be configured."
        )
    api_key = os.getenv(profile.api_key_env) if profile.api_key_env else None
    if profile.api_key_env and not api_key:
        raise ExtractionError(
            "invalid_configuration", "The model credential environment variable is missing."
        )
    return OpenAICompatibleGenerationProvider(
        descriptor=ModelDescriptor(
            model_id=profile.model_id,
            supports_text=profile.supports_text,
            supports_images=profile.supports_images,
            supports_native_json=profile.supports_native_json,
            max_input_chars=profile.max_input_chars,
            max_images=profile.max_images,
            concurrency=profile.concurrency,
        ),
        base_url=profile.base_url,
        api_key=api_key,
        connect_retries=profile.connect_retries,
    )


async def build_extraction_service(
    *,
    providers: Mapping[str, BaseGenerationProvider] | None = None,
    reader: BasePdfReader | None = None,
    settings: ExtractionSettings | None = None,
    config_path: Path | None = None,
    provider_factories: Mapping[str, ProviderFactory] | None = None,
    document_capability: BaseCapability[DocumentExtractionInput, DocumentResult] | None = None,
    fields_capability: BaseCapability[FieldExtractionInput, FieldExtractionResult] | None = None,
) -> ExtractionService:
    """Construct an isolated runtime with explicit extension points.

    Args:
        providers: Host-owned profile bindings; these override deployment bindings.
        reader: Optional replacement reader.
        settings: Optional validated behavior overrides.
        config_path: Deployment YAML path; defaults to packaged native-only configuration.
            Explicit ``${NAME}`` string placeholders resolve from the environment;
            missing or empty referenced values reject configuration before model setup.
        provider_factories: Additional explicitly registered provider implementations.
        document_capability: Replacement document operation for this runtime.
        fields_capability: Replacement schema-understanding operation for this runtime.

    Returns:
        A service that closes only providers constructed by this composition root.
    """
    config = await asyncio.to_thread(
        _read_config, config_path or Path(__file__).with_name("defaults.yaml")
    )
    behavior = ExtractionSettings.model_validate(settings or config.settings)
    factories: dict[str, ProviderFactory] = {"openai_compatible": _openai_factory}
    factories.update(provider_factories or {})
    bindings = dict(providers or {})
    owned: list[BaseGenerationProvider] = []
    try:
        for name, profile in config.profiles.items():
            if name in bindings:
                continue
            factory = factories.get(profile.provider)
            if factory is None:
                raise ExtractionError(
                    "invalid_configuration", "A configured provider factory is not registered."
                )
            provider = factory(profile)
            bindings[name] = provider
            owned.append(provider)
        gateway = ModelGateway(
            bindings,
            calls_per_second=behavior.calls_per_second,
            timeout_seconds=behavior.inference_timeout_seconds,
            pricing={
                name: profile.pricing
                for name, profile in config.profiles.items()
                if profile.pricing is not None
            },
            provider_names={name: profile.provider for name, profile in config.profiles.items()},
        )
        return ExtractionService(
            reader=reader or PdfReader(),
            gateway=gateway,
            settings=behavior,
            document_capability=document_capability,
            fields_capability=fields_capability,
            owned_providers=tuple(owned),
        )
    except Exception:  # noqa: BLE001 - sanitize arbitrary custom factory failures after cleanup
        await asyncio.gather(*(provider.aclose() for provider in owned), return_exceptions=True)
        raise ExtractionError(
            "invalid_configuration", "The extraction runtime could not be configured."
        ) from None
