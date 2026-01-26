import yaml
from pathlib import Path
from typing import Dict, Any

class ConfigLoader:
    """Utility for loading YAML configuration files."""
    
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
            return yaml.safe_load(f)
    
    @staticmethod
    def get_model_config(model_id: str, config_dir: Path = None) -> Dict[str, Any]:
        """Load configuration for a specific model.
        
        Args:
            model_id: Identifier of the model (e.g., 'qwen3-vl-30b').
            config_dir: Directory containing models.yaml. Defaults to 'configs/'.
            
        Returns:
            Model configuration dictionary.
            
        Raises:
            ValueError: If model_id is not found in configuration.
        """
        if config_dir is None:
            config_dir = Path(__file__).parent.parent.parent / "configs"
        
        models_config = ConfigLoader.load_yaml(config_dir / "models.yaml")
        
        if model_id not in models_config.get("models", {}):
            available = list(models_config.get("models", {}).keys())
            raise ValueError(f"Model '{model_id}' not found. Available: {available}")
        
        return models_config["models"][model_id]
    
    @staticmethod
    def get_pipeline_config(pipeline_name: str = "basic", config_dir: Path = None) -> Dict[str, Any]:
        """Load configuration for a pipeline.
        
        Args:
            pipeline_name: Name of the pipeline (default: 'basic').
            config_dir: Directory containing pipeline.yaml.
            
        Returns:
            Pipeline configuration dictionary.
        """
        if config_dir is None:
            config_dir = Path(__file__).parent.parent.parent / "configs"
        
        pipelines_config = ConfigLoader.load_yaml(config_dir / "pipeline.yaml")
        
        if pipeline_name not in pipelines_config.get("pipelines", {}):
            available = list(pipelines_config.get("pipelines", {}).keys())
            raise ValueError(f"Pipeline '{pipeline_name}' not found. Available: {available}")
        
        return pipelines_config["pipelines"][pipeline_name]
