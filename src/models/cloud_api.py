import os
from typing import Dict, Any, Union
from pathlib import Path
from src.core.base import BaseVisionLanguageModel

class CloudAPIModel(BaseVisionLanguageModel):
    """Generic adapter for Cloud APIs (OpenAI-compatible)."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.client = None
        self.model_name = config.get("model_name", "gpt-4o")
        self.api_key_env = config.get("config", {}).get("api_key_env", "OPENAI_API_KEY")
        self.base_url_env = config.get("config", {}).get("base_url_env", "OPENAI_BASE_URL")

    def load(self) -> None:
        """Initialize the API client."""
        # We import here to avoid hard dependency if not used
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError("openai package is required for CloudAPIModel. Install it with `pip install openai`.")
        
        api_key = os.getenv(self.api_key_env)
        base_url = os.getenv(self.base_url_env)

        if not api_key:
            # We don't raise error here to allow initialization, but process will fail
            print(f"WARNING: {self.api_key_env} not set.")
            
        self.client = OpenAI(api_key=api_key, base_url=base_url)

    def unload(self) -> None:
        """Nothing to unload for API client."""
        self.client = None

    def process(self, image: Union[str, Path, bytes], prompt: str, **kwargs) -> Dict[str, Any]:
        """Process content using the Cloud API."""
        if not self.client:
            raise RuntimeError("Model not loaded. Call load() first.")

        import base64
        import mimetypes

        messages = []
        
        # Handle Image Input
        if image:
            image_data = None
            mime_type = "image/jpeg" # Default

            if isinstance(image, (str, Path)):
                path = Path(image)
                if path.exists():
                    guessed_type, _ = mimetypes.guess_type(path)
                    if guessed_type:
                        mime_type = guessed_type
                    with open(path, "rb") as img_file:
                        image_data = base64.b64encode(img_file.read()).decode('utf-8')
            elif isinstance(image, bytes):
                image_data = base64.b64encode(image).decode('utf-8')
            
            if image_data:
                messages.append({
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{image_data}"
                            }
                        }
                    ]
                })
            else:
                # If image path provided but invalid/missing, fallback to just text
                messages.append({"role": "user", "content": prompt})
        else:
            messages.append({"role": "user", "content": prompt})
        
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                max_tokens=self.config.get("config", {}).get("max_tokens", 1024)
            )
            return {
                "content": response.choices[0].message.content,
                "raw_response": response.model_dump()
            }
        except Exception as e:
            return {"error": str(e)}
