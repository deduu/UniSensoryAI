import logging

from .loader import ModelLoader
from .cloud_api import CloudAPIModel

logger = logging.getLogger(__name__)

# Cloud providers are always registered — no heavy deps.
ModelLoader.register_loader("openai", CloudAPIModel)
ModelLoader.register_loader("google", CloudAPIModel)
ModelLoader.register_loader("together", CloudAPIModel)
ModelLoader.register_loader("fireworks", CloudAPIModel)
ModelLoader.register_loader("openrouter", CloudAPIModel)
ModelLoader.register_loader("deepinfra", CloudAPIModel)

# Local-VLM providers depend on torch/transformers/bitsandbytes (the
# `local-vlm` extras group). Skip registration if those aren't installed
# — the production CPU/cloud image deliberately omits them.
try:
    from .deepseek import DeepSeekModel
    from .llava import LLaVAModel
    from .qwen import QwenModel
    from .lightonocr import LightOnOCRModel

    ModelLoader.register_loader("deepseek", DeepSeekModel)
    ModelLoader.register_loader("llava", LLaVAModel)
    ModelLoader.register_loader("qwen", QwenModel)
    ModelLoader.register_loader("lightonocr", LightOnOCRModel)
except ImportError as e:
    logger.info(
        "Local-VLM providers disabled (torch/transformers not installed): %s. "
        "Install with `uv sync --extra local-vlm` to enable.",
        e,
    )

__all__ = ["ModelLoader", "CloudAPIModel"]
