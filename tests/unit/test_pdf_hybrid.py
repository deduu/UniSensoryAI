"""Tests for src/ingestion/pdf_hybrid.py — PageBundle extraction."""

import sys
from typing import Any, List, Tuple
from unittest.mock import MagicMock

import pytest
from PIL import Image


def _png_bytes(color: str = "red", size: Tuple[int, int] = (8, 8)) -> bytes:
    """Tiny PNG payload so the fake Pixmap can hand back something real."""
    import io as _io
    buf = _io.BytesIO()
    Image.new("RGB", size, color=color).save(buf, format="PNG")
    return buf.getvalue()


class _FakePixmap:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def tobytes(self, fmt: str = "png") -> bytes:
        return self._payload


class _FakeRect:
    def __init__(self, x0: float, y0: float, x1: float, y1: float) -> None:
        self.x0 = x0
        self.y0 = y0
        self.x1 = x1
        self.y1 = y1


class _FakePage:
    """Stands in for a ``fitz.Page`` in the unit tests."""

    def __init__(
        self,
        text: str,
        images: List[Any] | None = None,
        rects_by_xref: dict[int, List[_FakeRect]] | None = None,
        page_payload: bytes | None = None,
        region_payload: bytes | None = None,
    ) -> None:
        self._text = text
        self._images = images or []
        self._rects = rects_by_xref or {}
        self._page_payload = page_payload or _png_bytes("blue")
        self._region_payload = region_payload or _png_bytes("green")
        self.pixmap_calls: List[dict] = []

    def get_text(self, mode: str = "text") -> str:
        return self._text

    def get_images(self, full: bool = True) -> List[Any]:
        return self._images

    def get_image_rects(self, xref: int) -> List[_FakeRect]:
        return self._rects.get(xref, [])

    def get_pixmap(self, matrix: Any = None, clip: Any = None) -> _FakePixmap:
        self.pixmap_calls.append({"matrix": matrix, "clip": clip})
        return _FakePixmap(self._region_payload if clip is not None else self._page_payload)


@pytest.fixture
def fake_fitz(monkeypatch):
    """Stub the ``fitz`` module so extract_page_bundle runs without PyMuPDF.

    Provides ``Matrix`` and ``Rect`` callables that record their args, which
    is all ``extract_page_bundle`` needs.
    """
    fake = MagicMock()
    fake.Matrix = lambda x, y: ("matrix", x, y)
    fake.Rect = lambda r: r  # identity — extract_page_bundle just passes it through
    monkeypatch.setitem(sys.modules, "fitz", fake)
    yield fake


def test_digital_page_with_no_images_returns_text_only(fake_fitz):
    from src.ingestion.pdf_hybrid import extract_page_bundle

    page = _FakePage(text="Hello world. " * 20)
    bundle = extract_page_bundle(page, page_no=1)

    assert bundle.page_no == 1
    assert bundle.needs_full_page_vlm is False
    assert bundle.full_page_image is None
    assert bundle.image_regions == []
    assert "Hello world." in bundle.text_layer
    # No pixmap calls when there are no images.
    assert page.pixmap_calls == []


def test_scanned_page_falls_back_to_full_page_vlm(fake_fitz):
    from src.ingestion.pdf_hybrid import extract_page_bundle

    # Very short text (< 50 chars) → treated as scanned.
    page = _FakePage(text="   ")
    bundle = extract_page_bundle(page, page_no=3)

    assert bundle.needs_full_page_vlm is True
    assert bundle.text_layer == ""
    assert bundle.full_page_image is not None
    # One pixmap call for the full page (no clip).
    assert len(page.pixmap_calls) == 1
    assert page.pixmap_calls[0]["clip"] is None


def test_digital_page_with_embedded_figures_emits_regions(fake_fitz):
    from src.ingestion.pdf_hybrid import extract_page_bundle

    page = _FakePage(
        text="A long enough paragraph to clear the scanned threshold easily." * 2,
        images=[(1001,), (1002,)],  # two embedded images by xref
        rects_by_xref={
            1001: [_FakeRect(10, 10, 120, 80)],
            1002: [_FakeRect(0, 200, 300, 400)],
        },
    )
    bundle = extract_page_bundle(page, page_no=2)

    assert bundle.needs_full_page_vlm is False
    assert bundle.full_page_image is None
    assert len(bundle.image_regions) == 2
    assert {r.region_type for r in bundle.image_regions} == {"figure"}
    # Each region gets its own clipped pixmap call.
    assert len(page.pixmap_calls) == 2
    assert all(call["clip"] is not None for call in page.pixmap_calls)


def test_image_with_no_rects_is_skipped(fake_fitz):
    from src.ingestion.pdf_hybrid import extract_page_bundle

    page = _FakePage(
        text="Long enough page text to avoid being labeled as scanned. " * 3,
        images=[(2001,)],
        rects_by_xref={},  # no rects available for this xref
    )
    bundle = extract_page_bundle(page, page_no=4)

    assert bundle.image_regions == []
    assert page.pixmap_calls == []


def test_threshold_is_configurable(fake_fitz):
    from src.ingestion.pdf_hybrid import extract_page_bundle

    page = _FakePage(text="short")
    bundle = extract_page_bundle(page, page_no=1, text_threshold=2)

    # With threshold=2 and text "short" (len 5), this is NOT scanned.
    assert bundle.needs_full_page_vlm is False
    assert bundle.text_layer == "short"
