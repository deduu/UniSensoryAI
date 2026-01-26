from typing import Dict, Any, Union, Optional
from pathlib import Path
from abc import ABC, abstractmethod
import torch
from src.core.base import BaseVisionLanguageModel


class HuggingFaceBaseModel(BaseVisionLanguageModel, ABC):
    """Abstract base class for Hugging Face model implementations."""
    
    # Memory unit conversion constants
    BYTES_TO_GB = 1024 ** 3
    BYTES_TO_MB = 1024 ** 2
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.model = None
        self.processor = None
        self.model_name = config.get("model_name")
        self.device_map = config.get("config", {}).get("device_map", "auto")
        self.dtype_str = config.get("config", {}).get("dtype", "bfloat16")
    
    @abstractmethod
    def _get_model_class(self):
        """Return the model class to use for loading."""
        pass
    
    @abstractmethod
    def _get_processor_class(self):
        """Return the processor class to use for loading."""
        pass
    
    @abstractmethod
    def _prepare_inputs(self, img_obj, prompt: str) -> Dict[str, torch.Tensor]:
        """Prepare model-specific inputs."""
        pass
    
    @abstractmethod
    def _decode_output(self, inputs: Dict, generated_ids: torch.Tensor) -> str:
        """Decode model-specific output."""
        pass
    
    def _get_dtype(self) -> torch.dtype:
        """Convert dtype string to torch dtype."""
        dtype_map = {
            "bfloat16": torch.bfloat16,
            "float16": torch.float16,
            "float32": torch.float32,
        }
        return dtype_map.get(self.dtype_str, torch.bfloat16)
    
    def _setup_quantization(self) -> Optional[Any]:
        """Setup quantization config if specified."""
        quant_settings = self.config.get("config", {}).get("quantization")
        
        if not quant_settings or not quant_settings.get("load_in_4bit"):
            return None
        
        try:
            from transformers import BitsAndBytesConfig
            print("Loading model with 4-bit quantization...")
            
            return BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_compute_dtype=self._get_dtype(),
                bnb_4bit_quant_type=quant_settings.get("bnb_4bit_quant_type", "nf4"),
                bnb_4bit_use_double_quant=quant_settings.get("bnb_4bit_use_double_quant", False)
            )
        except ImportError:
            print("WARNING: bitsandbytes not found. Skipping 4-bit quantization.")
            return None
    
    def _parse_max_memory(self, max_memory_config: Dict[str, str]) -> Dict[Union[int, str], str]:
        """Parse max_memory config, converting string keys to int where possible."""
        max_memory = {}
        for k, v in max_memory_config.items():
            try:
                key = int(k)
            except ValueError:
                key = k
            max_memory[key] = v
        return max_memory
    
    def _log_memory_stats(self, stage: str = ""):
        """Log GPU memory statistics in a readable format."""
        if not torch.cuda.is_available():
            return
        
        try:
            device_count = torch.cuda.device_count()
            prefix = f"[{stage}] " if stage else ""
            
            for device_id in range(device_count):
                reserved = torch.cuda.memory_reserved(device_id) / self.BYTES_TO_GB
                allocated = torch.cuda.memory_allocated(device_id) / self.BYTES_TO_GB
                
                # Get total GPU memory
                props = torch.cuda.get_device_properties(device_id)
                total = props.total_memory / self.BYTES_TO_GB
                
                print(f"{prefix}GPU {device_id} ({props.name}): "
                      f"Allocated: {allocated:.2f}GB / Reserved: {reserved:.2f}GB / Total: {total:.2f}GB")
        except Exception as e:
            print(f"Could not retrieve memory stats: {e}")
    
    def load(self) -> None:
        """Load the model and processor."""
        try:
            import torch
        except ImportError:
            raise ImportError("torch package is required.")
        
        print(f"Loading {self.__class__.__name__}: {self.model_name}...")
        
        dtype = self._get_dtype()
        quantization_config = self._setup_quantization()
        
        # Prepare loading kwargs
        load_kwargs = {
            "device_map": self.device_map,
            "torch_dtype": dtype,
            "trust_remote_code": True,
            "low_cpu_mem_usage": True,
            "offload_buffers": True,
        }
        
        if quantization_config:
            load_kwargs["quantization_config"] = quantization_config
        
        # Add max_memory if specified
        max_memory_config = self.config.get("config", {}).get("max_memory")
        if max_memory_config:
            max_memory = self._parse_max_memory(max_memory_config)
            load_kwargs["max_memory"] = max_memory
            print(f"Applying max_memory limit: {max_memory}")
        
        # Load model
        model_class = self._get_model_class()
        self.model = model_class.from_pretrained(self.model_name, **load_kwargs)
        
        # Apply memory optimizations
        self.model.config.use_cache = False
        if hasattr(self.model, 'gradient_checkpointing_enable'):
            self.model.gradient_checkpointing_enable()
            print("Enabled gradient checkpointing for memory efficiency")
        
        # Cleanup and logging
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            self._log_memory_stats("After Model Load")
        
        # Model info
        model_size = self.model.get_memory_footprint() / self.BYTES_TO_GB
        print(f"Model weights footprint: {model_size:.2f}GB")
        
        if hasattr(self.model, "is_quantized"):
            print(f"Is quantized: {self.model.is_quantized}")
        
        if quantization_config:
            print(f"Quantization config: {quantization_config.to_dict()}")
        
        # Load processor
        processor_class = self._get_processor_class()
        self.processor = processor_class.from_pretrained(
            self.model_name,
            trust_remote_code=True
        )
        
        print(f"✓ {self.__class__.__name__} loaded successfully")
    
    def unload(self) -> None:
        """Unload model and free resources."""
        if self.model is not None:
            del self.model
        if self.processor is not None:
            del self.processor
        
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            self._log_memory_stats("After Unload")
        
        self.model = None
        self.processor = None
    
    def process(self, image: Union[str, Path, bytes], prompt: str, **kwargs) -> Dict[str, Any]:
        """Process image with prompt."""
        if not self.model:
            raise RuntimeError("Model not loaded. Call load() first.")
        
        import io
        from PIL import Image
        
        # Load image
        img_obj = self._load_image(image)
        if img_obj is None:
            return {"error": "Invalid image input"}
        
        # Resize image to reduce memory
        img_obj = self._resize_image(img_obj, kwargs.get("max_image_size", 768))
        
        # Prepare inputs
        inputs = self._prepare_inputs(img_obj, prompt)
        inputs = self._move_inputs_to_device(inputs)
        
        # Extract generation parameters
        gen_kwargs = self._extract_generation_kwargs(kwargs)
        
        # Generate
        with torch.inference_mode():
            generated_ids = self.model.generate(**inputs, **gen_kwargs)
        
        # Decode output
        output_text = self._decode_output(inputs, generated_ids)
        
        # Cleanup
        del inputs, generated_ids
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        
        return {"content": output_text}
    
    def _load_image(self, image: Union[str, Path, bytes]):
        """Load image from various sources."""
        import io
        from PIL import Image
        
        try:
            if isinstance(image, (str, Path)):
                return Image.open(image)
            elif isinstance(image, bytes):
                return Image.open(io.BytesIO(image))
            else:
                return None
        except Exception as e:
            print(f"Error loading image: {e}")
            return None
    
    def _resize_image(self, img_obj, max_size: int):
        """Resize image if larger than max_size."""
        if max(img_obj.size) > max_size:
            from PIL import Image
            img_obj.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
            print(f"Resized image to {img_obj.size} to reduce memory usage")
        return img_obj
    
    def _move_inputs_to_device(self, inputs: Dict[str, torch.Tensor]) -> Dict[str, torch.Tensor]:
        """Move inputs to model device."""
        device = self.model.device
        return {k: v.to(device) for k, v in inputs.items()}
    
    def _extract_generation_kwargs(self, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """Extract and validate generation parameters."""
        return {
            "max_new_tokens": kwargs.get("max_new_tokens", 128),
            "temperature": kwargs.get("temperature", 0.7),
            "top_p": kwargs.get("top_p", 0.9),
            "do_sample": kwargs.get("do_sample", True),
            "use_cache": False,  # Always disable for memory efficiency
        }
