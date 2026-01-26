import torch

from typing import Dict, Any, Union, Optional
from transformers import AutoModelForImageTextToText, AutoProcessor
from src.models.huggingface import HuggingFaceBaseModel

class LightOnOCRModel(HuggingFaceBaseModel):
    """LightOn OCR model implementation."""
    
    def _get_model_class(self):
        from transformers import LightOnOcrForConditionalGeneration
        return LightOnOcrForConditionalGeneration
    
    def _get_processor_class(self):
        from transformers import LightOnOcrProcessor
        return LightOnOcrProcessor
    
    def _prepare_inputs(self, img_obj, prompt: str) -> Dict[str, torch.Tensor]:
        # LightOn OCR doesn't use text prompts in the same way
        conversation = [{"role": "user", "content": [{"type": "image"}]}]
        
        inputs = self.processor.apply_chat_template(
            conversation,
            add_generation_prompt=True,
            tokenize=True,
            return_dict=True,
            return_tensors="pt",
        )
        
        # Handle dtype conversion for pixel values
        device = self.model.device
        dtype = next(self.model.parameters()).dtype
        
        processed_inputs = {}
        for k, v in inputs.items():
            if v.is_floating_point():
                processed_inputs[k] = v.to(device=device, dtype=dtype)
            else:
                processed_inputs[k] = v.to(device)
        
        return processed_inputs
    
    def _decode_output(self, inputs: Dict, generated_ids: torch.Tensor) -> str:
        generated_ids_trimmed = generated_ids[0, inputs["input_ids"].shape[1]:]
        return self.processor.decode(generated_ids_trimmed, skip_special_tokens=True)

