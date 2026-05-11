"""Tests for src/inference/concurrency.py — ModelSemaphoreRegistry."""

import asyncio
from unittest.mock import patch

import pytest

from src.inference.concurrency import (
    ModelSemaphoreRegistry,
    get_registry,
    reset_registry,
)


@pytest.fixture(autouse=True)
def _reset_singleton():
    reset_registry()
    yield
    reset_registry()


def _fake_config(provider: str, concurrency=None):
    cfg = {"provider": provider, "model_name": "fake"}
    if concurrency is not None:
        cfg["concurrency"] = concurrency
    return cfg


class TestLimitResolution:
    @pytest.mark.asyncio
    async def test_explicit_concurrency_wins(self):
        registry = ModelSemaphoreRegistry()
        with patch(
            "src.inference.concurrency.ConfigLoader.get_model_config",
            return_value=_fake_config("qwen", concurrency=7),
        ):
            await registry.get("any-model")
        assert registry.get_limit("any-model") == 7

    @pytest.mark.asyncio
    async def test_cloud_default(self):
        registry = ModelSemaphoreRegistry()
        with patch(
            "src.inference.concurrency.ConfigLoader.get_model_config",
            return_value=_fake_config("openai"),
        ):
            await registry.get("gpt-4o")
        assert registry.get_limit("gpt-4o") == 8

    @pytest.mark.asyncio
    async def test_local_default(self):
        registry = ModelSemaphoreRegistry()
        with patch(
            "src.inference.concurrency.ConfigLoader.get_model_config",
            return_value=_fake_config("qwen"),
        ):
            await registry.get("qwen-local")
        assert registry.get_limit("qwen-local") == 1

    @pytest.mark.asyncio
    async def test_unknown_provider_defaults_to_one(self):
        registry = ModelSemaphoreRegistry()
        with patch(
            "src.inference.concurrency.ConfigLoader.get_model_config",
            return_value=_fake_config("martian"),
        ):
            await registry.get("alien")
        assert registry.get_limit("alien") == 1

    @pytest.mark.asyncio
    async def test_config_read_failure_defaults_to_one(self):
        registry = ModelSemaphoreRegistry()
        with patch(
            "src.inference.concurrency.ConfigLoader.get_model_config",
            side_effect=RuntimeError("config gone"),
        ):
            await registry.get("missing")
        assert registry.get_limit("missing") == 1


class TestSemaphoreSemantics:
    @pytest.mark.asyncio
    async def test_same_model_returns_same_semaphore(self):
        registry = ModelSemaphoreRegistry()
        with patch(
            "src.inference.concurrency.ConfigLoader.get_model_config",
            return_value=_fake_config("openai", concurrency=4),
        ):
            a = await registry.get("m")
            b = await registry.get("m")
        assert a is b

    @pytest.mark.asyncio
    async def test_different_models_isolated(self):
        """Holding model A at its limit must not block model B."""
        registry = ModelSemaphoreRegistry()
        configs = {
            "model-a": _fake_config("qwen", concurrency=1),
            "model-b": _fake_config("openai", concurrency=4),
        }
        with patch(
            "src.inference.concurrency.ConfigLoader.get_model_config",
            side_effect=lambda model_id, validate=True: configs[model_id],
        ):
            sem_a = await registry.get("model-a")
            sem_b = await registry.get("model-b")

        # Saturate model-a — model-b must still be acquirable without blocking.
        await sem_a.acquire()
        assert sem_a.locked()
        acquired_b = await asyncio.wait_for(sem_b.acquire(), timeout=0.1)
        # Semaphore.acquire returns True on success (or just None on success
        # depending on Python version); both are truthy except None — accept either.
        assert acquired_b is None or acquired_b is True
        sem_b.release()
        sem_a.release()

    @pytest.mark.asyncio
    async def test_concurrency_actually_caps_parallelism(self):
        """At most ``limit`` coroutines may hold the semaphore at once."""
        registry = ModelSemaphoreRegistry()
        with patch(
            "src.inference.concurrency.ConfigLoader.get_model_config",
            return_value=_fake_config("openai", concurrency=2),
        ):
            sem = await registry.get("m")

        in_flight = 0
        max_in_flight = 0
        lock = asyncio.Lock()

        async def worker():
            nonlocal in_flight, max_in_flight
            async with sem:
                async with lock:
                    in_flight += 1
                    max_in_flight = max(max_in_flight, in_flight)
                await asyncio.sleep(0.02)
                async with lock:
                    in_flight -= 1

        await asyncio.gather(*[worker() for _ in range(8)])
        assert max_in_flight == 2


class TestSingleton:
    def test_get_registry_returns_singleton(self):
        a = get_registry()
        b = get_registry()
        assert a is b

    def test_reset_registry_replaces_instance(self):
        a = get_registry()
        reset_registry()
        b = get_registry()
        assert a is not b
