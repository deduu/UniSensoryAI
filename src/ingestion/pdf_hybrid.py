"""Hybrid PDF extraction.

Digital PDFs carry a real text layer; rendering them to images and re-OCRing
through a VLM is lossy and slow. This module extracts the text layer directly
via PyMuPDF and only renders image regions (figures and embedded images) for
VLM processing. Scanned PDFs — those with no usable text layer — fall back to
full-page VLM extraction, which matches what ChatGPT would do anyway.

The output is a :class:`PageBundle` per page; ``InferenceStage`` interprets
each bundle to decide which regions need a model call.
"""

from __future__ import annotations

import io
import logging
from dataclasses import dataclass, field
from typing import Any, List, Literal, Optional, Tuple

from PIL import Image

logger = logging.getLogger(__name__)

# A page whose extracted text layer is shorter than this (after stripping) is
# treated as scanned: we cannot trust the text and fall back to full-page VLM.
SCANNED_PAGE_TEXT_THRESHOLD = 50

RegionType = Literal["figure", "table", "page"]


@dataclass
class RegionImage:
    """A cropped image region inside a PDF page that needs VLM extraction.

    Attributes:
        image: Rendered crop of the region as a PIL image.
        region_type: ``"figure"`` for embedded images, ``"table"`` for table
            crops (Phase 2 only emits ``"figure"``; table detection is Phase 5).
        bbox: ``(x0, y0, x1, y1)`` in PDF coordinates.
    """

    image: Image.Image
    region_type: RegionType
    bbox: Tuple[float, float, float, float]


@dataclass
class PageBundle:
    """Hybrid extraction result for a single PDF page.

    A bundle carries the page's text layer (which may be the entire content
    on a digital PDF), plus zero-or-more image regions that need VLM, plus
    optionally a full-page rendering when the page is judged unusable as
    text (scanned).

    Attributes:
        page_no: 1-indexed page number.
        text_layer: Plain text extracted by PyMuPDF. May be empty for scanned pages.
        image_regions: Image crops that require VLM extraction.
        full_page_image: Rendered full page, only set when ``needs_full_page_vlm``.
        needs_full_page_vlm: True when the text layer is unusable (scanned page);
            ``InferenceStage`` must send ``full_page_image`` to the VLM.
    """

    page_no: int
    text_layer: str = ""
    image_regions: List[RegionImage] = field(default_factory=list)
    full_page_image: Optional[Image.Image] = None
    needs_full_page_vlm: bool = False


def _render_pixmap_to_image(pix: Any) -> Image.Image:
    """Convert a PyMuPDF Pixmap to a PIL Image via PNG round-trip."""
    return Image.open(io.BytesIO(pix.tobytes("png")))


def extract_page_bundle(
    page: Any,
    page_no: int,
    zoom: float = 2.0,
    text_threshold: int = SCANNED_PAGE_TEXT_THRESHOLD,
) -> PageBundle:
    """Extract a :class:`PageBundle` from one PyMuPDF page.

    Args:
        page: A ``fitz.Page`` (passed in by the caller; this module never
            imports fitz directly so the unit tests can fake it).
        page_no: 1-indexed page number used to label the bundle.
        zoom: Pixmap rendering zoom. Passed through to fitz.Matrix.
        text_threshold: If the stripped text layer is shorter than this, the
            page is treated as scanned.

    Returns:
        A populated :class:`PageBundle`.
    """
    import fitz  # local import so module import works without PyMuPDF

    text_layer: str = ""
    try:
        text_layer = page.get_text("text") or ""
    except Exception as exc:  # noqa: BLE001
        logger.warning("pdf_hybrid: get_text failed on page %d: %s", page_no, exc)

    is_scanned = len(text_layer.strip()) < text_threshold

    if is_scanned:
        # Render the whole page for VLM fallback. No regions, no text.
        try:
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat)
            full_image = _render_pixmap_to_image(pix)
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "pdf_hybrid: failed to render scanned page %d: %s", page_no, exc
            )
            full_image = None
        return PageBundle(
            page_no=page_no,
            text_layer="",
            image_regions=[],
            full_page_image=full_image,
            needs_full_page_vlm=True,
        )

    # Digital page: keep the text layer, render any embedded figures.
    regions: List[RegionImage] = []
    try:
        embedded = page.get_images(full=True)
    except Exception as exc:  # noqa: BLE001
        logger.warning("pdf_hybrid: get_images failed on page %d: %s", page_no, exc)
        embedded = []

    for img_meta in embedded:
        # img_meta is a tuple; xref is the first element.
        xref = img_meta[0]
        try:
            bbox_rects = page.get_image_rects(xref)
        except Exception as exc:  # noqa: BLE001
            logger.debug(
                "pdf_hybrid: get_image_rects failed (xref=%s page=%d): %s",
                xref,
                page_no,
                exc,
            )
            continue
        if not bbox_rects:
            continue
        # PyMuPDF returns a list of Rects (an image can appear multiple times).
        for rect in bbox_rects:
            try:
                clip = fitz.Rect(rect)
                mat = fitz.Matrix(zoom, zoom)
                pix = page.get_pixmap(matrix=mat, clip=clip)
                region_image = _render_pixmap_to_image(pix)
                regions.append(
                    RegionImage(
                        image=region_image,
                        region_type="figure",
                        bbox=(
                            float(rect.x0),
                            float(rect.y0),
                            float(rect.x1),
                            float(rect.y1),
                        ),
                    )
                )
            except Exception as exc:  # noqa: BLE001
                logger.debug(
                    "pdf_hybrid: failed to render figure xref=%s page=%d: %s",
                    xref,
                    page_no,
                    exc,
                )

    return PageBundle(
        page_no=page_no,
        text_layer=text_layer,
        image_regions=regions,
        full_page_image=None,
        needs_full_page_vlm=False,
    )
