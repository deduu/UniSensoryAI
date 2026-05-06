"""Tests for routing and agent modules."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock

from src.core.base import BaseAgent, ProcessingResult
from src.core.document import Document, DocumentType
from src.routing.type_router import TypeRouter, NoAgentFoundError
from src.agents.pdf_agent import PDFAgent
from src.agents.image_agent import ImageAgent
from src.agents.office_agent import OfficeAgent
from src.agents.excel_agent import ExcelParserAgent
from src.pipeline.stages.routing_stage import RoutingStage


# ---------------------------------------------------------------------------
# TypeRouter
# ---------------------------------------------------------------------------


class TestTypeRouter:
    def _make_doc(self, doc_type: DocumentType) -> Document:
        """Helper to create a minimal Document."""
        return Document(
            id="test-doc",
            file_path=Path("/fake/path.pdf"),
            document_type=doc_type,
        )

    @pytest.mark.asyncio
    async def test_selects_correct_agent_for_pdf(self):
        """Router should select PDFAgent for PDF documents."""
        router = TypeRouter()
        router.register_agent(PDFAgent(), priority=10)
        router.register_agent(ImageAgent(), priority=10)

        doc = self._make_doc(DocumentType.PDF)
        agent = await router.route(doc)
        assert agent.name == "PDFAgent"

    @pytest.mark.asyncio
    async def test_selects_correct_agent_for_image(self):
        """Router should select ImageAgent for image documents."""
        router = TypeRouter()
        router.register_agent(PDFAgent(), priority=10)
        router.register_agent(ImageAgent(), priority=10)

        doc = self._make_doc(DocumentType.IMAGE)
        agent = await router.route(doc)
        assert agent.name == "ImageAgent"

    @pytest.mark.asyncio
    async def test_selects_correct_agent_for_excel(self):
        """Router should select OfficeAgent (or ExcelParserAgent) for Excel."""
        router = TypeRouter()
        router.register_agent(OfficeAgent(), priority=10)
        router.register_agent(ExcelParserAgent(), priority=5)

        doc = self._make_doc(DocumentType.EXCEL)
        agent = await router.route(doc)
        # OfficeAgent has higher priority and handles Excel
        assert agent.name == "OfficeAgent"

    @pytest.mark.asyncio
    async def test_respects_priority(self):
        """Higher priority agent should be selected when multiple can handle."""
        router = TypeRouter()
        router.register_agent(OfficeAgent(name="LowPriority"), priority=1)
        router.register_agent(OfficeAgent(name="HighPriority"), priority=100)

        doc = self._make_doc(DocumentType.EXCEL)
        agent = await router.route(doc)
        assert agent.name == "HighPriority"

    @pytest.mark.asyncio
    async def test_raises_no_agent_found(self):
        """Router should raise NoAgentFoundError when no agent can handle."""
        router = TypeRouter()
        router.register_agent(PDFAgent(), priority=10)

        doc = self._make_doc(DocumentType.WEB)  # No agent for WEB
        with pytest.raises(NoAgentFoundError):
            await router.route(doc)

    def test_register_agent(self):
        """register_agent should add to the internal list."""
        router = TypeRouter()
        agent = PDFAgent()
        router.register_agent(agent, priority=5)

        assert len(router.registered_agents) == 1
        assert router.registered_agents[0] == (agent, 5)


# ---------------------------------------------------------------------------
# Agent can_handle
# ---------------------------------------------------------------------------


class TestAgentCanHandle:
    def _make_doc(self, doc_type: DocumentType) -> Document:
        return Document(
            id="test", file_path=Path("/fake"), document_type=doc_type
        )

    def test_pdf_agent_handles_pdf(self):
        assert PDFAgent().can_handle(self._make_doc(DocumentType.PDF)) is True

    def test_pdf_agent_rejects_image(self):
        assert PDFAgent().can_handle(self._make_doc(DocumentType.IMAGE)) is False

    def test_image_agent_handles_image(self):
        assert ImageAgent().can_handle(self._make_doc(DocumentType.IMAGE)) is True

    def test_image_agent_rejects_pdf(self):
        assert ImageAgent().can_handle(self._make_doc(DocumentType.PDF)) is False

    def test_office_agent_handles_word(self):
        assert OfficeAgent().can_handle(self._make_doc(DocumentType.WORD)) is True

    def test_office_agent_handles_powerpoint(self):
        assert OfficeAgent().can_handle(self._make_doc(DocumentType.POWERPOINT)) is True

    def test_office_agent_handles_excel(self):
        assert OfficeAgent().can_handle(self._make_doc(DocumentType.EXCEL)) is True

    def test_office_agent_rejects_pdf(self):
        assert OfficeAgent().can_handle(self._make_doc(DocumentType.PDF)) is False

    def test_excel_agent_handles_excel(self):
        assert ExcelParserAgent().can_handle(self._make_doc(DocumentType.EXCEL)) is True

    def test_excel_agent_rejects_word(self):
        assert ExcelParserAgent().can_handle(self._make_doc(DocumentType.WORD)) is False


# ---------------------------------------------------------------------------
# RoutingStage
# ---------------------------------------------------------------------------


class TestRoutingStage:
    def test_validate_input(self):
        """Requires document_type and file_path."""
        stage = RoutingStage()
        assert stage.validate_input({}) is False
        assert stage.validate_input({"document_type": "pdf"}) is False
        assert (
            stage.validate_input({"document_type": "pdf", "file_path": "/f.pdf"})
            is True
        )

    @pytest.mark.asyncio
    async def test_routes_pdf(self):
        """Should set selected_agent_name for PDF."""
        stage = RoutingStage()
        result = await stage.execute(
            {"document_type": "pdf", "file_path": "/test.pdf", "job_id": "j1"}
        )
        assert result["selected_agent_name"] == "PDFAgent"

    @pytest.mark.asyncio
    async def test_routes_image(self):
        """Should set selected_agent_name for image."""
        stage = RoutingStage()
        result = await stage.execute(
            {"document_type": "image", "file_path": "/test.png", "job_id": "j2"}
        )
        assert result["selected_agent_name"] == "ImageAgent"

    @pytest.mark.asyncio
    async def test_routes_excel(self):
        """Should set selected_agent_name for Excel."""
        stage = RoutingStage()
        result = await stage.execute(
            {"document_type": "excel", "file_path": "/test.xlsx", "job_id": "j3"}
        )
        assert result["selected_agent_name"] == "OfficeAgent"

    @pytest.mark.asyncio
    async def test_routes_word(self):
        """Should set selected_agent_name for Word."""
        stage = RoutingStage()
        result = await stage.execute(
            {"document_type": "word", "file_path": "/test.docx", "job_id": "j4"}
        )
        assert result["selected_agent_name"] == "OfficeAgent"
