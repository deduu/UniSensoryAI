from typing import Dict, Any, Union
from pathlib import Path
import torch
from src.core.base import BaseVisionLanguageModel

class HuggingFaceModel(BaseVisionLanguageModel):
    """Adapter for Hugging Face Transformers models (e.g. Qwen)."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.model = None
        self.processor = None
        self.model_name = config.get("model_name")
        self.device_map = config.get("config", {}).get("device_map", "auto")
        self.dtype_str = config.get("config", {}).get("dtype", "bfloat16")

    def load(self) -> None:
        try:
            from transformers import AutoModelForImageTextToText, AutoProcessor
            import torch
        except ImportError:
            raise ImportError("transformers and torch packages are required.")

        print(f"Loading HF model: {self.model_name}...")
        
        dtype = torch.bfloat16 if self.dtype_str == "bfloat16" else torch.float16
        if self.dtype_str == "float32":
            dtype = torch.float32

        # Note: In a real scenario, we might want to catch OOM errors here
        self.model = AutoModelForImageTextToText.from_pretrained(
            self.model_name,
            device_map=self.device_map,
            torch_dtype=dtype,
            trust_remote_code=True
        )
        self.processor = AutoProcessor.from_pretrained(
            self.model_name, 
            trust_remote_code=True
        )

    def unload(self) -> None:
        del self.model
        del self.processor
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        self.model = None

    def process(self, image: Union[str, Path, bytes], prompt: str, **kwargs) -> Dict[str, Any]:
        if not self.model:
            raise RuntimeError("Model not loaded.")
        
        import io
        from PIL import Image
        
        # Load image
        img_obj = None
        if isinstance(image, (str, Path)):
            img_obj = Image.open(image)
        elif isinstance(image, bytes):
            img_obj = Image.open(io.BytesIO(image))
            
        if not img_obj:
             return {"error": "Invalid image input"}

        # Prepare conversation for Qwen2-VL styling
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": img_obj},
                    {"type": "text", "text": prompt},
                ],
            }
        ]
        
        # Preprocessing
        text = self.processor.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        
        image_inputs, video_inputs = None, None
        
        # Try importing qwen_vl_utils if available, else standard
        try:
            from qwen_vl_utils import process_vision_info
            image_inputs, video_inputs = process_vision_info(messages)
            inputs = self.processor(
                text=[text],
                images=image_inputs,
                videos=video_inputs,
                padding=True,
                return_tensors="pt",
            )
        except ImportError:
            # Fallback for standard usage if qwen_vl_utils missing (might fail for complex Qwen)
            inputs = self.processor(
                text=[text],
                images=[img_obj],
                padding=True,
                return_tensors="pt",
            )
            
        inputs = inputs.to(self.model.device)

        # Inference
        generated_ids = self.model.generate(**inputs, max_new_tokens=1024)
        
        # Trim input tokens
        generated_ids_trimmed = [
            out_ids[len(in_ids) :] for in_ids, out_ids in zip(inputs.input_ids, generated_ids)
        ]
        
        output_text = self.processor.batch_decode(
            generated_ids_trimmed, skip_special_tokens=True, clean_up_tokenization_spaces=False
        )[0]

        return {"content": output_text}
