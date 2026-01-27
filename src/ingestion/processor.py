import logging
import asyncio
from pathlib import Path
from typing import Optional, Dict, Any
from src.utils.config import ConfigLoader
from src.models import ModelLoader
from src.ingestion.converter import DocumentConverter

logger = logging.getLogger(__name__)

# Global Model Cache
# Structure: {"model_id": model_instance}
MODEL_CACHE: Dict[str, Any] = {}
MODEL_LOCK = asyncio.Lock()


async def get_cached_model(model_id: str):
    """
    Retrieve model from cache or load it if not present.
    """
    async with MODEL_LOCK:
        if model_id in MODEL_CACHE:
            return MODEL_CACHE[model_id]

        logger.info(f"Model {model_id} not in cache. Loading...")
        try:
            model_config = ConfigLoader.get_model_config(model_id)
            model = ModelLoader.load_model(model_config)
            MODEL_CACHE[model_id] = model
            return model
        except Exception as e:
            logger.error(f"Failed to load model {model_id}: {e}")
            raise e


async def process_document_job(file_path: str) -> dict:
    """
    Background task to process a document.
    Handles PDF conversion, Office text extraction, and multi-page processing.
    """
    try:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        logger.info(f"Starting processing for file: {file_path}")

        # 1. Convert/Load Document content
        # Returns List[Image.Image] OR List[str]
        try:
            content_items = DocumentConverter.convert(path)
        except Exception as e:
            return {"error": f"Document conversion failed: {str(e)}"}

        if not content_items:
            return {"error": "No processable content found in document."}

        # 2. Get Cached Model
        model_id = "qwen2-vl-2b-instruct"
        model = await get_cached_model(model_id)

        # 3. Process Items (Pages/Slides/Sheets)
        results = []
        loop = asyncio.get_event_loop()

        from PIL import Image

        for i, item in enumerate(content_items):
            logger.info(f"Processing item {i+1}/{len(content_items)}...")

            if isinstance(item, str):
                # Text Path (Office Files)
                # We feed the text as part of the prompt
                analysis_prompt = (
                    f"Analyze the following document content and extract key information:\n\n{item}"
                )

                page_result = await loop.run_in_executor(
                    None, lambda: model.process(prompt=analysis_prompt, image=None)
                )
                results.append(page_result.get("content", ""))

            elif isinstance(item, Image.Image):
                # Visual Path (Images/PDF)
                prompt = "Analyze this page/image and extract the whole content in detail."

                # Convert PIL to bytes
                import io

                img_byte_arr = io.BytesIO()
                item.save(img_byte_arr, format="PNG")
                img_bytes = img_byte_arr.getvalue()

                page_result = await loop.run_in_executor(
                    None, lambda: model.process(image=img_bytes, prompt=prompt)
                )
                results.append(page_result.get("content", ""))

        # 4. Aggregate Results
        full_content = "\n\n--- ITEM BREAK ---\n\n".join(results)

        logger.info(f"Processing complete for {file_path}")

        return {"content": full_content, "page_count": len(content_items)}

    except Exception as e:
        logger.error(f"Failed to process document {file_path}: {e}", exc_info=True)
        raise
