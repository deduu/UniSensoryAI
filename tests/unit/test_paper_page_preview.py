"""Original-page review must be bounded, model-free, and tenant-scoped."""

import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pymupdf
import pytest
from fastapi import FastAPI
from pydantic import ValidationError

from src.api.auth import UserContext, get_user_context
from src.api.paper_extraction_routes import get_history_service, get_page_preview_service, router
from src.services.pdf_page_preview import PdfPagePreviewService


def _pdf(path: Path) -> Path:
    with pymupdf.open() as document:
        page = document.new_page(width=72, height=144)
        page.draw_rect(page.rect, color=(1, 0, 0), fill=(1, 0, 0))
        page = document.new_page(width=144, height=72)
        page.draw_rect(page.rect, color=(0, 0, 1), fill=(0, 0, 1))
        document.save(path)
    return path


@pytest.mark.asyncio
async def test_render_selects_original_page_and_preserves_aspect_ratio(tmp_path: Path) -> None:
    path = _pdf(tmp_path / "source.pdf")
    renderer = PdfPagePreviewService()
    first = await renderer.render(path, 1)
    second = await renderer.render(path, 2)
    assert first.startswith(b"\x89PNG\r\n\x1a\n")
    first_image = pymupdf.Pixmap(first)
    second_image = pymupdf.Pixmap(second)
    assert first_image.height == first_image.width * 2
    assert second_image.width == second_image.height * 2
    assert first_image.pixel(20, 20)[:3] == (255, 0, 0)
    assert second_image.pixel(20, 20)[:3] == (0, 0, 255)


@pytest.mark.asyncio
async def test_render_rejects_page_absent_from_original(tmp_path: Path) -> None:
    path = _pdf(tmp_path / "source.pdf")
    with pytest.raises(FileNotFoundError):
        await PdfPagePreviewService().render(path, 3)


@pytest.mark.asyncio
@pytest.mark.parametrize("page", [0, -1, 501, True, "1"])
async def test_render_validates_page_input(tmp_path: Path, page: object) -> None:
    with pytest.raises(ValidationError):
        await PdfPagePreviewService().render(tmp_path / "unused.pdf", page)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_render_rejects_damaged_and_oversized_sources(tmp_path: Path) -> None:
    path = tmp_path / "damaged.pdf"
    path.write_bytes(b"%PDF-1.7 invalid")
    with pytest.raises(ValueError, match="Original PDF cannot be rendered"):
        await PdfPagePreviewService().render(path, 1)
    path = _pdf(tmp_path / "source.pdf")
    with pytest.raises(ValueError, match="size limit"):
        await PdfPagePreviewService(max_file_bytes=10).render(path, 1)


@pytest.mark.asyncio
async def test_render_caps_bitmap_size_for_large_pages(tmp_path: Path) -> None:
    path = tmp_path / "large.pdf"
    with pymupdf.open() as document:
        document.new_page(width=10000, height=10000)
        document.save(path)
    image = pymupdf.Pixmap(await PdfPagePreviewService(max_pixels=10000).render(path, 1))
    assert image.width * image.height <= 10000


def _app(history: SimpleNamespace, renderer: SimpleNamespace) -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_history_service] = lambda: history
    app.dependency_overrides[get_page_preview_service] = lambda: renderer
    app.dependency_overrides[get_user_context] = lambda: UserContext(
        user_id="reviewer", tenant_id="tenant-a", roles=["accountant"]
    )
    return app


@pytest.mark.asyncio
async def test_route_checks_tenant_before_reading_or_rendering() -> None:
    history = SimpleNamespace(find_job=AsyncMock(return_value=None))
    renderer = SimpleNamespace(render=AsyncMock())
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=_app(history, renderer)), base_url="http://test"
    ) as client:
        response = await client.get("/v1/paper/extractions/job-a/pages/1")
    assert response.status_code == 404
    history.find_job.assert_awaited_once_with("job-a", "tenant-a")
    renderer.render.assert_not_awaited()


@pytest.mark.asyncio
async def test_route_serves_only_authorized_source(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("UPLOADS_DIR", str(tmp_path))
    path = _pdf(tmp_path / "source.pdf")
    history = SimpleNamespace(find_job=AsyncMock(return_value=SimpleNamespace(file_path=str(path))))
    renderer = SimpleNamespace(render=AsyncMock(return_value=b"png-data"))
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=_app(history, renderer)), base_url="http://test"
    ) as client:
        response = await client.get("/v1/paper/extractions/job-a/pages/2")
        invalid = await client.get("/v1/paper/extractions/job-a/pages/501")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.headers["cache-control"] == "private, no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.content == b"png-data"
    renderer.render.assert_awaited_once_with(path, 2)
    assert invalid.status_code == 422


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error,status",
    [
        (FileNotFoundError(), 404),
        (ValueError("secret"), 503),
        (asyncio.TimeoutError("secret"), 503),
    ],
)
async def test_route_maps_renderer_errors_without_private_details(
    tmp_path: Path, monkeypatch, error: Exception, status: int
) -> None:
    monkeypatch.setenv("UPLOADS_DIR", str(tmp_path))
    path = _pdf(tmp_path / "source.pdf")
    history = SimpleNamespace(find_job=AsyncMock(return_value=SimpleNamespace(file_path=str(path))))
    renderer = SimpleNamespace(render=AsyncMock(side_effect=error))
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=_app(history, renderer)), base_url="http://test"
    ) as client:
        response = await client.get("/v1/paper/extractions/job-a/pages/1")
    assert response.status_code == status
    assert "secret" not in response.text
