"""PDF document processing agent."""

import logging
from typing import Optional

from src.core.base import BaseAgent, BaseVisionLanguageModel, ProcessingResult
from src.core.document import Document, DocumentType

logger = logging.getLogger(__name__)


class PDFAgent(BaseAgent):
    """Agent for processing PDF documents using Vision-Language Models.

    PDFs are rendered as images (one per page) and each page is sent
    to the VLM for content extraction.
    """

    def __init__(
        self,
        name: str = "PDFAgent",
        model: Optional[BaseVisionLanguageModel] = None,
    ) -> None:
        super().__init__(name=name, model=model)

    def can_handle(self, document: Document) -> bool:
        """Check if this agent can handle the document."""
        return document.document_type == DocumentType.PDF

    async def process(self, document: Document, **kwargs) -> ProcessingResult:
        """Process a PDF document.

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

            from src.ingestion.converter import DocumentConverter

            images = DocumentConverter.convert(document.file_path)

            if not images:
                result.status = "failed"
                result.errors.append("No pages extracted from PDF")
                return result

            import io

            extracted_pages = []
            for i, img in enumerate(images):
                img_bytes = io.BytesIO()
                img.save(img_bytes, format="PNG")
                page_result = self.model.process(
                    image=img_bytes.getvalue(),
                    prompt="Analyze this page and extract the whole content in detail.",
                )
                extracted_pages.append(page_result.get("content", ""))

            result.extracted_content = {
                "pages": extracted_pages,
                "page_count": len(images),
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
