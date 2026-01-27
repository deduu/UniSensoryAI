import torch

from typing import Dict, Any, Union, Optional
from transformers import AutoModelForImageTextToText, AutoProcessor
from src.models.huggingface import HuggingFaceBaseModel


class QwenModel(HuggingFaceBaseModel):
    """Qwen2-VL model implementation."""

    def _get_model_class(self):
        from transformers import AutoModelForImageTextToText

        return AutoModelForImageTextToText

    def _get_processor_class(self):
        from transformers import AutoProcessor

        return AutoProcessor

    def _prepare_inputs(self, img_obj, prompt: str) -> Dict[str, torch.Tensor]:
        content = [{"type": "text", "text": prompt}]
        if img_obj is not None:
            content.insert(0, {"type": "image", "image": img_obj})

        messages = [{"role": "user", "content": content}]

        text = self.processor.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )

        # Try qwen_vl_utils if available
        try:
            from qwen_vl_utils import process_vision_info

            image_inputs, video_inputs = process_vision_info(messages)

            inputs_kwargs = {}
            if image_inputs:
                inputs_kwargs["images"] = image_inputs
            if video_inputs:
                inputs_kwargs["videos"] = video_inputs

            return self.processor(text=[text], padding=True, return_tensors="pt", **inputs_kwargs)
        except ImportError:
            inputs_kwargs = {}
            if img_obj is not None:
                inputs_kwargs["images"] = [img_obj]

            return self.processor(text=[text], padding=True, return_tensors="pt", **inputs_kwargs)

    def _decode_output(self, inputs: Dict, generated_ids: torch.Tensor) -> str:
        # Access input_ids from dictionary, not as attribute
        generated_ids_trimmed = [
            out_ids[len(in_ids) :] for in_ids, out_ids in zip(inputs["input_ids"], generated_ids)
        ]
        return self.processor.batch_decode(
            generated_ids_trimmed, skip_special_tokens=True, clean_up_tokenization_spaces=False
        )[0]
