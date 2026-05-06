"""Routing stage — selects the appropriate agent for a document."""

import logging
from pathlib import Path
from typing import Any, Dict

from src.core.base import BasePipelineStage
from src.core.document import Document, DocumentType
from src.routing.type_router import TypeRouter
from src.agents.pdf_agent import PDFAgent
from src.agents.image_agent import ImageAgent
from src.agents.office_agent import OfficeAgent
from src.agents.excel_agent import ExcelParserAgent

logger = logging.getLogger(__name__)

# Map string document types to DocumentType enum
_STR_TO_DOCTYPE: Dict[str, DocumentType] = {
    "pdf": DocumentType.PDF,
    "image": DocumentType.IMAGE,
    "excel": DocumentType.EXCEL,
    "word": DocumentType.WORD,
    "powerpoint": DocumentType.POWERPOINT,
    "web": DocumentType.WEB,
    "code": DocumentType.CODE,
}


def _build_default_router() -> TypeRouter:
    """Create a router with all default agents registered."""
    router = TypeRouter()
    router.register_agent(PDFAgent(), priority=10)
    router.register_agent(ImageAgent(), priority=10)
    router.register_agent(OfficeAgent(), priority=10)
    router.register_agent(ExcelParserAgent(), priority=5)  # Lower priority fallback
    return router


class RoutingStage(BasePipelineStage):
    """Selects the best agent for the document based on its type.

    Reads:
        - ``document_type`` (str, set by IngestionStage)
        - ``file_path``

    Writes:
        - ``selected_agent_name`` (str)
    """

    def __init__(self, name: str = "routing") -> None:
        super().__init__(name=name)
        self._router = _build_default_router()

    def validate_input(self, context: Dict[str, Any]) -> bool:
        """Require document_type and file_path."""
        return (
            context.get("document_type") is not None
            and context.get("file_path") is not None
        )

    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Route the document to an agent.

        Args:
            context: Pipeline context dict.

        Returns:
            Updated context with ``selected_agent_name``.
        """
        doc_type_str = context["document_type"]
        doc_type = _STR_TO_DOCTYPE.get(doc_type_str, DocumentType.UNKNOWN)

        # Build a lightweight Document for routing
        document = Document(
            id=context.get("job_id", ""),
            file_path=Path(context["file_path"]),
            document_type=doc_type,
        )

        agent = await self._router.route(document)
        context["selected_agent_name"] = agent.name

        logger.info(
            "Routing stage: type=%s → agent=%s",
            doc_type_str,
            agent.name,
        )
        return context
