"""Bounded original PDF rendering, isolated from OCR and model inference."""

import asyncio
import math
from pathlib import Path

import pymupdf  # type: ignore[import-untyped]
from pydantic import BaseModel, ConfigDict, Field

from src.services.base_pdf_page_preview import BasePdfPagePreview


class _PreviewSettings(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

    dpi: int = Field(default=120, ge=72, le=220)
    max_file_bytes: int = Field(default=100 * 1024 * 1024, ge=1, le=100 * 1024 * 1024)
    max_pixels: int = Field(default=10_000_000, ge=4096, le=10_000_000)
    timeout_seconds: float = Field(default=15.0, gt=0, le=15.0)


class _PageRequest(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")

    path: Path
    page_number: int = Field(ge=1, le=500)


class PdfPagePreviewService(BasePdfPagePreview):
    """Render one authorized original page off the event loop."""

    def __init__(
        self,
        *,
        dpi: int = 120,
        max_file_bytes: int = 100 * 1024 * 1024,
        max_pixels: int = 10_000_000,
        timeout_seconds: float = 15.0,
    ) -> None:
        """Configure host-owned preview quality and resource budgets.

        Args:
            dpi: Requested resolution, downscaled to satisfy the pixel budget.
            max_file_bytes: Maximum original PDF input size.
            max_pixels: Maximum output image pixel count.
            timeout_seconds: Maximum elapsed rendering deadline.
        """
        self._settings = _PreviewSettings(
            dpi=dpi,
            max_file_bytes=max_file_bytes,
            max_pixels=max_pixels,
            timeout_seconds=timeout_seconds,
        )

    async def render(self, path: Path, page_number: int) -> bytes:
        """Render a source page with file, page, bitmap and elapsed-time limits.

        Args:
            path: Source file previously authorized and resolved by the host.
            page_number: One-based source PDF page, from 1 through 500.

        Returns:
            RGB PNG bytes, downscaled when the page exceeds the pixel budget.

        Raises:
            FileNotFoundError: The source or selected page does not exist.
            ValueError: The source is invalid, encrypted, or exceeds a safety limit.
            TimeoutError: Rendering exceeds the host's bounded preview deadline.
        """
        request = _PageRequest(path=path, page_number=page_number)
        return await asyncio.wait_for(
            asyncio.to_thread(self._render, request), self._settings.timeout_seconds
        )

    def _render(self, request: _PageRequest) -> bytes:
        if request.path.stat().st_size > self._settings.max_file_bytes:
            raise ValueError("Original PDF exceeds preview size limit.")
        try:
            with pymupdf.open(request.path) as document:
                if document.needs_pass or not document.is_pdf or document.page_count > 500:
                    raise ValueError("Original PDF cannot be rendered.")
                if request.page_number > document.page_count:
                    raise FileNotFoundError("Original PDF page does not exist.")
                page = document[request.page_number - 1]
                width, height = page.rect.width, page.rect.height
                if not all(math.isfinite(size) and size > 0 for size in (width, height)):
                    raise ValueError("Original PDF cannot be rendered.")
                scale = min(
                    self._settings.dpi / 72,
                    math.sqrt(self._settings.max_pixels / (width * height)),
                )
                while (
                    math.ceil(width * scale) * math.ceil(height * scale) > self._settings.max_pixels
                ):
                    scale *= 0.99
                image = page.get_pixmap(
                    matrix=pymupdf.Matrix(scale, scale), colorspace=pymupdf.csRGB, alpha=False
                )
                return bytes(image.tobytes("png"))
        except FileNotFoundError:
            raise
        except (RuntimeError, ValueError, pymupdf.FileDataError) as error:
            raise ValueError("Original PDF cannot be rendered.") from error
