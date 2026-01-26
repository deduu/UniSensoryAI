from .loader import ModelLoader
from .huggingface import HuggingFaceModel
from .deepseek import DeepSeekModel
from .cloud_api import CloudAPIModel

# Register default providers
ModelLoader.register_loader("huggingface", HuggingFaceModel)
ModelLoader.register_loader("deepseek", DeepSeekModel)
ModelLoader.register_loader("openai", CloudAPIModel)
ModelLoader.register_loader("google", CloudAPIModel) # Re-use generic cloud loader for now

__all__ = ["ModelLoader", "HuggingFaceModel", "DeepSeekModel", "CloudAPIModel"]
