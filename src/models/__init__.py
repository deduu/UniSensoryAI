from .loader import ModelLoader
# from .huggingface import HuggingFaceModel
from .deepseek import DeepSeekModel
from .cloud_api import CloudAPIModel
from .llava import LLaVAModel
from .qwen import QwenModel
from .lightonocr import LightOnOCRModel


# Register HuggingFace model implementations
# ModelLoader.register_loader("huggingface", HuggingFaceModel)
ModelLoader.register_loader("deepseek", DeepSeekModel)

ModelLoader.register_loader("llava", LLaVAModel)
ModelLoader.register_loader("qwen", QwenModel)
ModelLoader.register_loader("lightonocr", LightOnOCRModel)

#Register other providers
# Re-use generic cloud loader for now
ModelLoader.register_loader("openai", CloudAPIModel)
ModelLoader.register_loader("google", CloudAPIModel)

__all__ = ["ModelLoader", "HuggingFaceModel", "DeepSeekModel", "CloudAPIModel", "LLaVAModel", "QwenModel", "LightOnOCRModel"]
