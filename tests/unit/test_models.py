"""Tests for src/models/loader.py — model factory registry."""

import pytest
from unittest.mock import MagicMock
from src.models.loader import ModelLoader


def test_model_loader_registry_has_all_providers():
    """All 6 providers should be registered after import."""
    # Importing src.models triggers __init__.py which registers loaders
    import src.models  # noqa: F401

    expected = {"qwen", "deepseek", "llava", "lightonocr", "openai", "google"}
    registered = set(ModelLoader._loaders.keys())
    assert expected.issubset(registered), f"Missing providers: {expected - registered}"


def test_model_loader_unknown_provider_raises():
    """Loading a model with unknown provider should raise ValueError."""
    config = {"provider": "nonexistent_provider", "model_name": "fake"}
    with pytest.raises(ValueError, match="Unknown model provider"):
        ModelLoader.load_model(config)


def test_model_loader_load_calls_load():
    """load_model should instantiate the class and call .load() on it."""
    mock_cls = MagicMock()
    mock_instance = MagicMock()
    mock_cls.return_value = mock_instance

    # Temporarily register a test provider
    ModelLoader.register_loader("_test_provider", mock_cls)
    try:
        config = {"provider": "_test_provider", "model_name": "test-model"}
        result = ModelLoader.load_model(config)

        mock_cls.assert_called_once_with(config)
        mock_instance.load.assert_called_once()
        assert result is mock_instance
    finally:
        # Clean up
        del ModelLoader._loaders["_test_provider"]
