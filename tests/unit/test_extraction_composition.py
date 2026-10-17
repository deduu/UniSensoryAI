"""Composition must be configurable without application or model side effects."""

import json
from pathlib import Path

import pytest

from src.extraction.composition import build_extraction_service
from src.extraction.contracts import ModelDescriptor, ModelRequest, ModelResponse
from src.extraction.ports import BaseGenerationProvider
from src.extraction.provider_profile import ProviderProfile


class FakeProvider(BaseGenerationProvider):
    def __init__(self) -> None:
        self.closed = False

    @property
    def descriptor(self) -> ModelDescriptor:
        return ModelDescriptor(model_id="host")

    async def complete(self, request: ModelRequest) -> ModelResponse:
        return ModelResponse(content=json.dumps({"data": {}, "evidence": []}), model_id="host")

    async def aclose(self) -> None:
        self.closed = True


@pytest.mark.asyncio
async def test_build_without_provider_is_valid_for_native_only() -> None:
    service = await build_extraction_service()
    assert service is not None
    await service.aclose()


@pytest.mark.asyncio
async def test_host_provider_is_never_closed_by_service() -> None:
    provider = FakeProvider()
    service = await build_extraction_service(providers={"fields": provider})
    await service.aclose()
    assert not provider.closed


@pytest.mark.asyncio
async def test_yaml_behavior_and_provider_factories_are_extendable(tmp_path: Path) -> None:
    config = tmp_path / "extraction.yaml"
    config.write_text(
        "settings:\n  page_separator: '\\nNEXT\\n'\nprofiles:\n  fields:\n    provider: host\n    model_id: fake\n",
        encoding="utf-8",
    )
    built = []

    def factory(profile: ProviderProfile) -> FakeProvider:
        built.append(profile.model_id)
        return FakeProvider()

    service = await build_extraction_service(
        config_path=config, provider_factories={"host": factory}
    )
    assert built == ["fake"]
    await service.aclose()


@pytest.mark.asyncio
async def test_invalid_config_does_not_echo_secrets(tmp_path: Path) -> None:
    config = tmp_path / "extraction.yaml"
    config.write_text("settings:\n  field_attempts: 999\nsecret: private-value\n", encoding="utf-8")
    with pytest.raises(Exception) as error:
        await build_extraction_service(config_path=config)
    assert "private-value" not in str(error.value)


@pytest.mark.asyncio
async def test_factory_failure_closes_every_constructed_provider_safely(tmp_path: Path) -> None:
    from unittest.mock import AsyncMock

    from src.extraction.errors import ExtractionError

    config = tmp_path / "extraction.yaml"
    config.write_text(
        "profiles:\n  first:\n    provider: host\n    model_id: a\n  second:\n    provider: host\n    model_id: b\n  third:\n    provider: absent\n    model_id: c\n",
        encoding="utf-8",
    )
    first, second = FakeProvider(), FakeProvider()
    first.aclose = AsyncMock(side_effect=RuntimeError("private-value"))
    second.aclose = AsyncMock()
    providers = iter([first, second])
    with pytest.raises(ExtractionError) as error:
        await build_extraction_service(
            config_path=config, provider_factories={"host": lambda profile: next(providers)}
        )
    second.aclose.assert_awaited_once()
    assert "private-value" not in str(error.value)
    assert error.value.__cause__ is None


@pytest.mark.asyncio
async def test_deployment_profiles_expand_explicit_environment_placeholders(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TEST_EXTRACTION_MODEL", "host-model-${literal}")
    monkeypatch.setenv("TEST_EXTRACTION_URL", "https://host.example/v1")
    config = tmp_path / "extraction.yaml"
    config.write_text(
        "profiles:\n  vision:\n    provider: host\n"
        "    model_id: ${TEST_EXTRACTION_MODEL}\n"
        "    base_url: ${TEST_EXTRACTION_URL}\n",
        encoding="utf-8",
    )
    built: list[ProviderProfile] = []

    def factory(profile: ProviderProfile) -> FakeProvider:
        built.append(profile)
        return FakeProvider()

    service = await build_extraction_service(
        config_path=config, provider_factories={"host": factory}
    )
    assert built[0].model_id == "host-model-${literal}"
    assert built[0].base_url == "https://host.example/v1"
    await service.aclose()


@pytest.mark.parametrize("environment_value", [None, ""])
@pytest.mark.asyncio
async def test_unresolved_configuration_environment_fails_before_constructing_provider(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    environment_value: str | None,
) -> None:
    from src.extraction.errors import ExtractionError

    if environment_value is None:
        monkeypatch.delenv("TEST_MISSING_EXTRACTION_MODEL", raising=False)
    else:
        monkeypatch.setenv("TEST_MISSING_EXTRACTION_MODEL", environment_value)
    config = tmp_path / "extraction.yaml"
    config.write_text(
        "profiles:\n  fields:\n    provider: host\n"
        "    model_id: ${TEST_MISSING_EXTRACTION_MODEL}\n",
        encoding="utf-8",
    )
    built: list[ProviderProfile] = []

    def factory(profile: ProviderProfile) -> FakeProvider:
        built.append(profile)
        return FakeProvider()

    with pytest.raises(ExtractionError) as caught:
        await build_extraction_service(config_path=config, provider_factories={"host": factory})
    assert caught.value.code == "invalid_configuration"
    assert "TEST_MISSING" not in str(caught.value)
    assert not built


@pytest.mark.asyncio
async def test_application_configuration_binds_logical_profiles_without_model_hardcoding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EXTRACTION_MODEL", "deployment-selected-model")
    monkeypatch.setenv("EXTRACTION_BASE_URL", "https://host.example/v1")
    built: list[ProviderProfile] = []

    def factory(profile: ProviderProfile) -> FakeProvider:
        built.append(profile)
        return FakeProvider()

    config = Path(__file__).parents[2] / "configs" / "extraction.yaml"
    service = await build_extraction_service(
        config_path=config, provider_factories={"openai_compatible": factory}
    )
    assert len(built) == 2
    assert {profile.model_id for profile in built} == {"deployment-selected-model"}
    assert {profile.base_url for profile in built} == {"https://host.example/v1"}
    assert [profile.supports_images for profile in built] == [True, False]
    assert all(profile.api_key_env == "EXTRACTION_API_KEY" for profile in built)
    assert all(not profile.supports_native_json for profile in built)
    await service.aclose()
