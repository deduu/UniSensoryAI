from typing import Dict, Type, Any
from src.core.base import BaseVisionLanguageModel

class ModelLoader:
    """Factory for creating and loading models."""
    _loaders: Dict[str, Type[BaseVisionLanguageModel]] = {}

    @classmethod
    def register_loader(cls, provider: str, loader_cls: Type[BaseVisionLanguageModel]) -> None:
        """Register a new model loader class for a provider."""
        cls._loaders[provider.lower()] = loader_cls

    @classmethod
    def load_model(cls, config: Dict[str, Any]) -> BaseVisionLanguageModel:
        """Load a model based on configuration."""
        provider = config.get("provider", "").lower()
        if provider not in cls._loaders:
            raise ValueError(f"Unknown model provider: {provider}. Available: {list(cls._loaders.keys())}")
        
        loader_cls = cls._loaders[provider]
        model = loader_cls(config)
        model.load()
        return model
