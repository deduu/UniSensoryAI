"""PDF normalization with bounded raster assets and original page evidence."""

import asyncio
import base64
import hashlib
import math
from pathlib import Path
from threading import Event, Lock
from typing import Any, Literal

from src.extraction.contracts import (
    DocumentResult,
    ExtractionIssue,
    ExtractionOptions,
    ImageAsset,
    PageContent,
    PdfSource,
    TableContent,
    TextBlock,
)
from src.extraction.errors import ExtractionError
from src.extraction.ports.pdf_reader import BasePdfReader

# MuPDF table detection uses process-global character/edge buffers and tool
# settings. Reader instances therefore share a worker-side normalization lock.
_PDF_READ_LOCK = Lock()


class PdfReader(BasePdfReader):
    """Read PDF text, tables, and images without creating a model dependency."""

    async def read(self, source: PdfSource, options: ExtractionOptions) -> DocumentResult:
        """Normalize selected pages off the event loop.

        Args:
            source: Validated local path or in-memory PDF bytes.
            options: Page selection, output mode, and bounded resource settings.

        Returns:
            Ordered pages and full native text with self-contained PNG assets.
            All source bounding boxes use displayed page coordinates in PDF points,
            consistent with page width, height, and the full-page raster.

        Raises:
            ExtractionError: Input is invalid, encrypted, or exceeds a resource budget.
        """
        cancelled = Event()
        try:
            return await asyncio.to_thread(_read_serialized, source, options, cancelled)
        except asyncio.CancelledError:
            cancelled.set()
            raise


def _read_serialized(
    source: PdfSource, options: ExtractionOptions, cancelled: Event
) -> DocumentResult:
    with _PDF_READ_LOCK:
        if cancelled.is_set():
            raise ExtractionError(
                "workflow_cancelled", "PDF extraction was cancelled before reading."
            )
        return _read_sync(source, options)


def _read_payload(source: PdfSource, options: ExtractionOptions) -> bytes:
    if source.path is None:
        payload = source.data or b""
        filename = source.filename
    else:
        filename = source.path.name
        try:
            with source.path.open("rb") as handle:
                payload = handle.read(options.max_bytes + 1)
        except OSError:
            raise ExtractionError("source_unavailable", "The PDF source is unavailable.") from None
    if Path(filename).suffix.lower() != ".pdf":
        raise ExtractionError("invalid_pdf", "The source must have a PDF filename.")
    if len(payload) > options.max_bytes:
        raise ExtractionError("input_too_large", "The PDF exceeds the input byte limit.")
    if not payload.startswith(b"%PDF-"):
        raise ExtractionError("invalid_pdf", "The source is not a valid PDF.")
    return payload


def _read_sync(source: PdfSource, options: ExtractionOptions) -> DocumentResult:
    payload = _read_payload(source, options)
    # The canonical name avoids test suites that replace the legacy fitz alias.
    try:
        import pymupdf as fitz  # type: ignore[import-not-found]
    except ImportError:
        import fitz  # type: ignore[import-not-found]

    try:
        document = fitz.open(stream=payload, filetype="pdf")
    except Exception:  # noqa: BLE001 - parser errors must not disclose document bytes
        raise ExtractionError("invalid_pdf", "The source is not a readable PDF.") from None
    try:
        with document:
            if document.needs_pass or document.is_encrypted:
                raise ExtractionError("encrypted_pdf", "Encrypted PDFs are not supported.")
            count = document.page_count
            start = options.start_page or 1
            end = options.end_page or count
            if count == 0 or start > count or end > count:
                raise ExtractionError(
                    "invalid_page_range", "The requested page range does not exist in the PDF."
                )
            if end - start + 1 > options.max_pages:
                raise ExtractionError(
                    "page_limit_exceeded", "The selected PDF exceeds the page limit."
                )

            pages: list[PageContent] = []
            warnings: list[ExtractionIssue] = []
            used_asset_bytes = 0
            for page_number in range(start, end + 1):
                page = document.load_page(page_number - 1)
                text_blocks = _text_blocks(page, page_number)
                is_scanned = not text_blocks
                images: list[ImageAsset] = []
                tables: tuple[TableContent, ...] = ()
                if options.content_mode == "multimodal":
                    tables = _tables(page, page_number, warnings)
                if options.content_mode == "multimodal" or (
                    options.text_strategy == "native_then_ocr" and not is_scanned
                ):
                    # Each placement is rendered in its page context: repeated images,
                    # masks, rotations, and captions retain their visible location.
                    for image_number, image_info in enumerate(page.get_image_info(), start=1):
                        rect = (fitz.Rect(image_info["bbox"]) * page.rotation_matrix) & page.rect
                        if rect.is_empty or rect.is_infinite:
                            continue
                        asset, size = _raster_asset(
                            page,
                            rect,
                            f"p{page_number}-image-{image_number}",
                            page_number,
                            "image",
                            options,
                            used_asset_bytes,
                        )
                        used_asset_bytes += size
                        images.append(asset)
                if options.content_mode == "multimodal" or (
                    is_scanned and options.text_strategy == "native_then_ocr"
                ):
                    asset, size = _raster_asset(
                        page,
                        page.rect,
                        f"p{page_number}-page",
                        page_number,
                        "page",
                        options,
                        used_asset_bytes,
                    )
                    used_asset_bytes += size
                    images.append(asset)
                pages.append(
                    PageContent(
                        page_number=page_number,
                        width=page.rect.width,
                        height=page.rect.height,
                        text_blocks=text_blocks,
                        images=tuple(images),
                        tables=tables,
                        is_scanned=is_scanned,
                    )
                )
            return DocumentResult(
                document_id=hashlib.sha256(payload).hexdigest(),
                source_name=source.path.name if source.path else Path(source.filename).name,
                content_mode=options.content_mode,
                text="\n\n".join(
                    "\n".join(block.text for block in page.text_blocks) for page in pages
                ),
                pages=tuple(pages),
                warnings=tuple(warnings),
            )
    except ExtractionError:
        raise
    except Exception:  # noqa: BLE001 - sanitize library failures at the file boundary
        raise ExtractionError(
            "pdf_read_failed", "The PDF could not be normalized safely."
        ) from None


def _text_blocks(page: Any, page_number: int) -> tuple[TextBlock, ...]:
    blocks: list[TextBlock] = []
    for block in page.get_text("blocks", sort=True):
        # Image pseudo-blocks contain descriptions, not native document text.
        if block[6] != 0 or not str(block[4]).strip():
            continue
        blocks.append(
            TextBlock(
                block_id=f"p{page_number}-text-{len(blocks) + 1}",
                page_number=page_number,
                text=str(block[4]).rstrip("\n"),
                bbox=_display_bbox(page, block[:4]),
            )
        )
    return tuple(blocks)


def _tables(
    page: Any, page_number: int, warnings: list[ExtractionIssue]
) -> tuple[TableContent, ...]:
    if not hasattr(page, "find_tables"):
        warnings.append(
            ExtractionIssue(
                code="native_tables_unavailable",
                message="The PDF library does not support native table detection.",
                page_number=page_number,
            )
        )
        return ()
    rotation = page.rotation
    matrix = page.rotation_matrix
    try:
        # Detect semantic rows in the underlying content orientation; convert
        # only the resulting source rectangle to displayed page coordinates.
        # PyMuPDF otherwise rotates both the grid and its cell ordering.
        if rotation:
            page.set_rotation(0)
        found = page.find_tables()
        return tuple(
            TableContent(
                table_id=f"p{page_number}-table-{index}",
                page_number=page_number,
                rows=tuple(tuple(cell for cell in row) for row in table.extract()),
                bbox=_bbox(page.rect.__class__(table.bbox) * matrix),
            )
            for index, table in enumerate(found.tables, start=1)
        )
    except Exception:  # noqa: BLE001 - optional native table failures produce a diagnostic
        warnings.append(
            ExtractionIssue(
                code="table_extraction_failed",
                message="Native table detection was unavailable for this page.",
                page_number=page_number,
            )
        )
        return ()
    finally:
        if rotation:
            page.set_rotation(rotation)


def _raster_asset(
    page: Any,
    rect: Any,
    asset_id: str,
    page_number: int,
    kind: Literal["image", "page"],
    options: ExtractionOptions,
    used_bytes: int,
) -> tuple[ImageAsset, int]:
    scale = options.render_dpi / 72
    pixels = math.ceil(rect.width * scale) * math.ceil(rect.height * scale)
    # Bound temporary decompressed raster allocation as well as encoded output.
    if pixels * 3 > options.max_asset_bytes:
        raise ExtractionError("asset_limit_exceeded", "PDF image assets exceed the byte limit.")
    pixmap = page.get_pixmap(dpi=options.render_dpi, clip=rect, alpha=False)
    data = pixmap.tobytes("png")
    if used_bytes + len(data) > options.max_asset_bytes:
        raise ExtractionError("asset_limit_exceeded", "PDF image assets exceed the byte limit.")
    return (
        ImageAsset(
            asset_id=asset_id,
            page_number=page_number,
            data_base64=base64.b64encode(data).decode("ascii"),
            bbox=_bbox(rect),
            kind=kind,
        ),
        len(data),
    )


def _bbox(coordinates: Any) -> tuple[float, float, float, float]:
    return (
        float(coordinates[0]),
        float(coordinates[1]),
        float(coordinates[2]),
        float(coordinates[3]),
    )


def _display_bbox(page: Any, coordinates: Any) -> tuple[float, float, float, float]:
    return _bbox(page.rect.__class__(coordinates) * page.rotation_matrix)
