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
