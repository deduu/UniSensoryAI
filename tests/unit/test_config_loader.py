"""Tests for src/utils/config.py — ConfigLoader YAML parsing and model config resolution."""

import pytest
from unittest.mock import patch
from src.utils.config import ConfigLoader


class TestLoadYaml:
    def test_load_yaml_valid(self):
        """Loading models.yaml should return a dict with 'models' key."""
        config = ConfigLoader.load_yaml(ConfigLoader.DEFAULT_CONFIG_DIR / "models.yaml")
        assert isinstance(config, dict)
        assert "models" in config

    def test_load_yaml_missing_file(self, tmp_path):
        """Loading non-existent file should raise FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            ConfigLoader.load_yaml(tmp_path / "nonexistent.yaml")


class TestGetModelConfig:
    def test_get_model_config_known(self):
        """Known model ID should return a valid config dict with provider and model_name."""
        config = ConfigLoader.get_model_config("qwen2-vl-2b-instruct")
        assert "provider" in config
        assert "model_name" in config
        assert config["provider"] == "qwen"

    def test_get_model_config_unknown(self):
        """Unknown model ID should raise ValueError."""
        with pytest.raises(ValueError, match="not found"):
            ConfigLoader.get_model_config("nonexistent-model-xyz")


class TestResolveProvider:
    def test_resolve_provider_qwen(self):
        """huggingface + Qwen model name should resolve to 'qwen'."""
        config = {"provider": "huggingface", "model_name": "Qwen/Qwen2-VL-2B"}
        assert ConfigLoader._resolve_provider(config) == "qwen"

    def test_resolve_provider_llava(self):
        """huggingface + llava model name should resolve to 'llava'."""
        config = {"provider": "huggingface", "model_name": "llava-hf/llava-1.5-7b-hf"}
        assert ConfigLoader._resolve_provider(config) == "llava"

    def test_resolve_provider_lighton(self):
        """huggingface + lighton model name should resolve to 'lightonocr'."""
        config = {"provider": "huggingface", "model_name": "lightonai/LightOnOCR-2-1B-base"}
        assert ConfigLoader._resolve_provider(config) == "lightonocr"

    def test_resolve_provider_non_huggingface_passthrough(self):
        """Non-huggingface providers should pass through unchanged."""
        config = {"provider": "openai", "model_name": "gpt-4o"}
        assert ConfigLoader._resolve_provider(config) == "openai"

    def test_resolve_provider_default_to_qwen(self):
        """Unknown huggingface model should default to qwen."""
        config = {"provider": "huggingface", "model_name": "some-unknown/model"}
        assert ConfigLoader._resolve_provider(config) == "qwen"


class TestExpandEnvVars:
    def test_expand_env_vars_success(self):
        """Keys ending in _env should be expanded to env var values."""
        with patch.dict("os.environ", {"MY_API_KEY": "secret123"}):
            config = {"api_key_env": "MY_API_KEY", "other_field": "keep"}
            result = ConfigLoader._expand_env_vars(config)
            assert result["api_key"] == "secret123"
            assert result["other_field"] == "keep"
            assert "api_key_env" not in result

    def test_expand_env_vars_missing_skips(self):
        """Missing env var should be silently skipped."""
        config = {"api_key_env": "NONEXISTENT_VAR_XYZ_123"}
        result = ConfigLoader._expand_env_vars(config)
        assert "api_key" not in result
        assert "api_key_env" not in result

    def test_expand_env_vars_nested(self):
        """Nested dicts should be recursively expanded."""
        with patch.dict("os.environ", {"NESTED_KEY": "nested_value"}):
            config = {"outer": {"inner_env": "NESTED_KEY"}}
            result = ConfigLoader._expand_env_vars(config)
            assert result["outer"]["inner"] == "nested_value"


class TestListMethods:
    def test_list_available_models(self):
        """Should return a non-empty list of model ID strings."""
        models = ConfigLoader.list_available_models()
        assert isinstance(models, list)
        assert len(models) > 0
        assert "qwen2-vl-2b-instruct" in models

    def test_list_available_pipelines(self):
        """Should return available pipeline names."""
        pipelines = ConfigLoader.list_available_pipelines()
        assert isinstance(pipelines, list)
        assert "basic" in pipelines

    def test_get_models_by_provider_qwen(self):
        """Should filter models by resolved provider."""
        qwen_models = ConfigLoader.get_models_by_provider("qwen")
        assert isinstance(qwen_models, list)
        assert "qwen2-vl-2b-instruct" in qwen_models


class TestGetPolicyConfig:
    def test_get_policy_config(self):
        """Policy config should load web search and trusted source settings."""
        config = ConfigLoader.get_policy_config()
        assert "web_search" in config
        assert config["web_search"]["provider"] == "duckduckgo"
        assert "trusted_sources" in config
        assert len(config["trusted_sources"]["sources"]) >= 1
