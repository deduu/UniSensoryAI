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
        quantization_config = None
        quant_settings = self.config.get("config", {}).get("quantization")
        
        if quant_settings and quant_settings.get("load_in_4bit"):
            try:
                from transformers import BitsAndBytesConfig
                print("Loading model with 4-bit quantization...")
                quantization_config = BitsAndBytesConfig(
                    load_in_4bit=True,
                    bnb_4bit_compute_dtype=dtype,
                    bnb_4bit_quant_type=quant_settings.get("bnb_4bit_quant_type", "nf4"),
                    bnb_4bit_use_double_quant=quant_settings.get("bnb_4bit_use_double_quant", False)
                )
            except ImportError:
                print("WARNING: bitsandbytes not found. Skipping 4-bit quantization.")

        # Prepare loading kwargs
        load_kwargs = {
            "device_map": self.device_map,
            "torch_dtype": dtype,
            "trust_remote_code": True,
            "low_cpu_mem_usage": True,
            "offload_buffers": True,  # Help with memory management
        }
        
        if quantization_config:
            load_kwargs["quantization_config"] = quantization_config
            
        # Add max_memory from config if present
        max_memory_config = self.config.get("config", {}).get("max_memory")
        if max_memory_config:
            # Convert keys to int if possible (for GPU IDs)
            max_memory = {}
            for k, v in max_memory_config.items():
                try:
                   key = int(k)
                except ValueError:
                   key = k
                max_memory[key] = v
            load_kwargs["max_memory"] = max_memory
            print(f"Applying max_memory limit: {max_memory}")

        self.model = AutoModelForImageTextToText.from_pretrained(
            self.model_name,
            **load_kwargs
        )
        
        # OOM prevention: disable cache and enable gradient checkpointing
        self.model.config.use_cache = False
        if hasattr(self.model, 'gradient_checkpointing_enable'):
            self.model.gradient_checkpointing_enable()
            print("Enabled gradient checkpointing for memory efficiency")
        
        # Cleanup and Logging
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            reserved = torch.cuda.memory_reserved() / 1024**3
            allocated = torch.cuda.memory_allocated() / 1024**3
            print(f"CUDA Memory: Allocated: {allocated:.2f} GB | Reserved: {reserved:.2f} GB")
        
        # Verification logging
        model_size = self.model.get_memory_footprint()
        print(f"Model loaded. Memory footprint (Weights): {model_size / 1024**3:.2f} GB")
        if hasattr(self.model, "is_quantized"):
             print(f"Is quantized: {self.model.is_quantized}")
        
        if quantization_config:
            print(f"Quantization config used: {quantization_config.to_dict()}")
            
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

        # Resize image to reduce memory usage
        max_size = kwargs.get("max_image_size", 768)
        if max(img_obj.size) > max_size:
            img_obj.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
            print(f"Resized image to {img_obj.size} to reduce memory usage")

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

        # Extract generation parameters from kwargs
        max_new_tokens = kwargs.get("max_new_tokens", 256)  # Reduced default from 1024
        temperature = kwargs.get("temperature", 0.7)
        top_p = kwargs.get("top_p", 0.9)
        do_sample = kwargs.get("do_sample", True)
        
        # Inference with memory-efficient settings
        with torch.inference_mode():  # More efficient than torch.no_grad()
            generated_ids = self.model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                temperature=temperature,
                top_p=top_p,
                do_sample=do_sample,
                use_cache=False,  # Disable KV cache to save memory
            )
        
        # Trim input tokens
        generated_ids_trimmed = [
            out_ids[len(in_ids) :] for in_ids, out_ids in zip(inputs.input_ids, generated_ids)
        ]
        
        output_text = self.processor.batch_decode(
            generated_ids_trimmed, skip_special_tokens=True, clean_up_tokenization_spaces=False
        )[0]

        # Clear memory after inference
        del inputs, generated_ids, generated_ids_trimmed
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

        return {"content": output_text}