import os
from pathlib import Path
from typing import Any, Dict, Optional

import yaml
from dotenv import load_dotenv

# Load .env file so env vars are available for config expansion
load_dotenv()


class ConfigLoader:
    """Utility for loading YAML configuration files."""
    
    # Default config directory
    DEFAULT_CONFIG_DIR = Path(__file__).parent.parent.parent / "configs"
    
    @staticmethod
    def load_yaml(config_path: Path) -> Dict[str, Any]:
        """Load and parse a YAML configuration file.
        
        Args:
            config_path: Path to the YAML file.
            
        Returns:
            Dictionary containing the parsed YAML.
            
        Raises:
            FileNotFoundError: If the config file doesn't exist.
            yaml.YAMLError: If the YAML is malformed.
        """
        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")
        
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        return config if config is not None else {}
    
    @staticmethod
    def _resolve_provider(model_config: Dict[str, Any]) -> str:
        """Determine the provider to use for model loading.
        
        Maps legacy 'huggingface' provider to specific model types (qwen, llava, etc.)
        based on model_name or explicit model_type_specific field.
        
        Args:
            model_config: Model configuration dictionary.
            
        Returns:
            Provider string for ModelLoader.
        """
        provider = model_config.get("provider", "").lower()
        
        # If provider is not 'huggingface', return as-is
        if provider != "huggingface":
            return provider
        
        # Check for explicit provider override
        if "provider_specific" in model_config:
            return model_config["provider_specific"].lower()
        
        # Auto-detect from model_name
        model_name = model_config.get("model_name", "").lower()
        
        if "qwen" in model_name:
            return "qwen"
        elif "llava" in model_name:
            return "llava"
        elif "lighton" in model_name or "lightocr" in model_name:
            return "lightonocr"
        
        # Default to qwen for unknown huggingface models
        # (you can change this to raise an error if preferred)
        return "qwen"
    
    @staticmethod
    def _validate_model_config(model_id: str, model_config: Dict[str, Any]) -> None:
        """Validate model configuration has required fields.
        
        Args:
            model_id: Model identifier.
            model_config: Model configuration dictionary.
            
        Raises:
            ValueError: If required fields are missing.
        """
        required_fields = ["provider", "model_name"]
        missing = [f for f in required_fields if f not in model_config]
        
        if missing:
            raise ValueError(
                f"Model '{model_id}' missing required fields: {missing}"
            )
    
    @staticmethod
    def _expand_env_vars(config: Dict[str, Any], overrides: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """Recursively expand environment variables in config values.
        
        Looks for values ending with '_env' and replaces them with actual env var values.
        Example: api_key_env: "OPENAI_API_KEY" -> api_key: <actual value>
        
        Args:
            config: Configuration dictionary.
            overrides: Optional dictionary of environment variable overrides.
            
        Returns:
            Configuration with environment variables expanded.
        """
        result = {}
        overrides = overrides or {}
        
        for key, value in config.items():
            if isinstance(value, dict):
                result[key] = ConfigLoader._expand_env_vars(value, overrides)
            elif isinstance(key, str) and isinstance(value, str) and key.endswith("_env"):
                # Replace _env key with actual key and resolve env var
                actual_key = key[:-4]  # Remove '_env' suffix
                env_value = overrides.get(value) or os.getenv(value)
                if env_value is not None:
                    result[actual_key] = env_value
                # Skip silently if not set — downstream code validates required fields
            else:
                result[key] = value
        
        return result
    
    @staticmethod
    def get_model_config(
        model_id: str, 
        config_dir: Optional[Path] = None,
        validate: bool = True,
        api_keys: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """Load configuration for a specific model.
        
        Args:
            model_id: Identifier of the model (e.g., 'qwen2-vl-2b-instruct').
            config_dir: Directory containing models.yaml. Defaults to 'configs/'.
            validate: Whether to validate the configuration.
            api_keys: Optional overrides for environment variables (API keys).
            
        Returns:
            Model configuration dictionary ready for ModelLoader.
            
        Raises:
            ValueError: If model_id is not found or config is invalid.
        """
        if config_dir is None:
            config_dir = ConfigLoader.DEFAULT_CONFIG_DIR
        
        models_config = ConfigLoader.load_yaml(config_dir / "models.yaml")
        
        if model_id not in models_config.get("models", {}):
            available = list(models_config.get("models", {}).keys())
            raise ValueError(
                f"Model '{model_id}' not found in models.yaml. "
                f"Available models: {available}"
            )
        
        model_config = models_config["models"][model_id].copy()
        
        if validate:
            ConfigLoader._validate_model_config(model_id, model_config)
        
        # Resolve the actual provider for ModelLoader
        model_config["provider"] = ConfigLoader._resolve_provider(model_config)
        
        # Expand environment variables
        if "config" in model_config:
            model_config["config"] = ConfigLoader._expand_env_vars(
                model_config["config"], overrides=api_keys
            )
        
        return model_config
    
    @staticmethod
    def get_pipeline_config(
        pipeline_name: str = "basic", 
        config_dir: Optional[Path] = None
    ) -> Dict[str, Any]:
        """Load configuration for a pipeline.
        
        Args:
            pipeline_name: Name of the pipeline (default: 'basic').
            config_dir: Directory containing pipeline.yaml.
            
        Returns:
            Pipeline configuration dictionary.
            
        Raises:
            ValueError: If pipeline_name is not found.
        """
        if config_dir is None:
            config_dir = ConfigLoader.DEFAULT_CONFIG_DIR
        
        pipelines_config = ConfigLoader.load_yaml(config_dir / "pipeline.yaml")
        
        if pipeline_name not in pipelines_config.get("pipelines", {}):
            available = list(pipelines_config.get("pipelines", {}).keys())
            raise ValueError(
                f"Pipeline '{pipeline_name}' not found in pipeline.yaml. "
                f"Available pipelines: {available}"
            )
        
        return pipelines_config["pipelines"][pipeline_name]

    @staticmethod
    def get_policy_config(config_dir: Optional[Path] = None) -> Dict[str, Any]:
        """Load policy review configuration."""
        if config_dir is None:
            config_dir = ConfigLoader.DEFAULT_CONFIG_DIR
        return ConfigLoader.load_yaml(config_dir / "policy.yaml")
    
    @staticmethod
    def list_available_models(config_dir: Optional[Path] = None) -> list[str]:
        """List all available model IDs.
        
        Args:
            config_dir: Directory containing models.yaml.
            
        Returns:
            List of model IDs.
        """
        if config_dir is None:
            config_dir = ConfigLoader.DEFAULT_CONFIG_DIR
        
        models_config = ConfigLoader.load_yaml(config_dir / "models.yaml")
        return list(models_config.get("models", {}).keys())
    
    @staticmethod
    def list_available_pipelines(config_dir: Optional[Path] = None) -> list[str]:
        """List all available pipeline names.
        
        Args:
            config_dir: Directory containing pipeline.yaml.
            
        Returns:
            List of pipeline names.
        """
        if config_dir is None:
            config_dir = ConfigLoader.DEFAULT_CONFIG_DIR
        
        pipelines_config = ConfigLoader.load_yaml(config_dir / "pipeline.yaml")
        return list(pipelines_config.get("pipelines", {}).keys())
    
    @staticmethod
    def get_models_by_provider(
        provider: str, 
        config_dir: Optional[Path] = None
    ) -> list[str]:
        """Get all model IDs for a specific provider.
        
        Args:
            provider: Provider name (e.g., 'qwen', 'openai', 'deepseek').
            config_dir: Directory containing models.yaml.
            
        Returns:
            List of model IDs for the provider.
        """
        if config_dir is None:
            config_dir = ConfigLoader.DEFAULT_CONFIG_DIR
        
        models_config = ConfigLoader.load_yaml(config_dir / "models.yaml")
        
        matching_models = []
        for model_id, config in models_config.get("models", {}).items():
            resolved_provider = ConfigLoader._resolve_provider(config)
            if resolved_provider == provider.lower():
                matching_models.append(model_id)
        
        return matching_models
