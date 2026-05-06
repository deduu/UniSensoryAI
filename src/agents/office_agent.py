"""Office document processing agent — handles Word, PowerPoint, and Excel files."""

import logging
from typing import Optional

from src.core.base import BaseAgent, BaseVisionLanguageModel, ProcessingResult
from src.core.document import Document, DocumentType

logger = logging.getLogger(__name__)


class OfficeAgent(BaseAgent):
    """Agent for processing Office documents (DOCX, PPTX, XLSX).

    Office files are converted to text by DocumentConverter, then the
    text is sent to the VLM for analysis and structured extraction.
    """

    _HANDLED_TYPES = {DocumentType.WORD, DocumentType.POWERPOINT, DocumentType.EXCEL}

    def __init__(
        self,
        name: str = "OfficeAgent",
        model: Optional[BaseVisionLanguageModel] = None,
    ) -> None:
        super().__init__(name=name, model=model)

    def can_handle(self, document: Document) -> bool:
        """Check if this agent can handle the document."""
        return document.document_type in self._HANDLED_TYPES

    async def process(self, document: Document, **kwargs) -> ProcessingResult:
        """Process an Office document.

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

            text_items = DocumentConverter.convert(document.file_path)

            if not text_items:
                result.status = "failed"
                result.errors.append("No content extracted from document")
                return result

            extracted_sections = []
            for i, text in enumerate(text_items):
                analysis_prompt = (
                    "Analyze the following document content and extract "
                    f"key information:\n\n{text}"
                )
                section_result = self.model.process(
                    prompt=analysis_prompt,
                    image=None,
                )
                extracted_sections.append(section_result.get("content", ""))

            result.extracted_content = {
                "sections": extracted_sections,
                "section_count": len(text_items),
                "metadata": {
                    "agent": self.name,
                    "document_type": document.document_type.value,
                },
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
