"""Image document processing agent."""

import logging
from typing import Optional

from src.core.base import BaseAgent, BaseVisionLanguageModel, ProcessingResult
from src.core.document import Document, DocumentType

logger = logging.getLogger(__name__)


class ImageAgent(BaseAgent):
    """Agent for processing standalone image files using Vision-Language Models.

    Handles PNG, JPG, JPEG, BMP, TIFF, WEBP formats.
    """

    def __init__(
        self,
        name: str = "ImageAgent",
        model: Optional[BaseVisionLanguageModel] = None,
    ) -> None:
        super().__init__(name=name, model=model)

    def can_handle(self, document: Document) -> bool:
        """Check if this agent can handle the document."""
        return document.document_type == DocumentType.IMAGE

    async def process(self, document: Document, **kwargs) -> ProcessingResult:
        """Process an image document.

        Args:
            document: Document to process.
            **kwargs: Additional processing parameters.

        Returns:
            ProcessingResult with extracted content.
        """
        result = ProcessingResult(
            document_id=document.id,
            status="processing",
        )

        try:
            if not self.model:
                result.status = "failed"
                result.errors.append("No model configured")
                return result

            import io

            from PIL import Image

            img = Image.open(document.file_path)
            img_bytes = io.BytesIO()
            img.save(img_bytes, format="PNG")

            page_result = self.model.process(
                image=img_bytes.getvalue(),
                prompt="Analyze this image and extract all content in detail.",
            )

            result.extracted_content = {
                "content": page_result.get("content", ""),
                "metadata": {"agent": self.name},
            }
            result.status = "completed"

        except Exception as e:
            result.status = "failed"
            result.errors.append(str(e))

        return result

    def validate(self, result: ProcessingResult) -> bool:
        """Validate processing result."""
        if result.status != "completed":
            return False
        if not result.extracted_content:
            return False
        return True
