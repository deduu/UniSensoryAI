"""Real PDF coverage for the model-independent reader contract."""

import asyncio
import base64
import hashlib
import io
import random
import threading
from pathlib import Path

import pymupdf
import pytest
from PIL import Image

from src.extraction.contracts import DocumentResult, ExtractionOptions, PdfSource
from src.extraction.errors import ExtractionError
from src.extraction.pdf_reader import PdfReader


def _pdf(*texts: str) -> bytes:
    with pymupdf.open() as document:
        for text in texts:
            page = document.new_page(width=400, height=500)
            if text:
                page.insert_text((40, 60), text)
        return document.tobytes()


def _image_pdf() -> bytes:
    stream = io.BytesIO()
    Image.new("RGB", (40, 30), "blue").save(stream, format="PNG")
    with pymupdf.open() as document:
        digital = document.new_page(width=400, height=500)
        digital.insert_text((40, 60), "PO-123")
        digital.insert_image(pymupdf.Rect(40, 100, 120, 160), stream=stream.getvalue())
        scanned = document.new_page(width=400, height=500)
        scanned.insert_image(pymupdf.Rect(0, 0, 400, 500), stream=stream.getvalue())
        return document.tobytes()


@pytest.mark.asyncio
async def test_native_only_keeps_all_pages_short_text_and_stable_evidence() -> None:
    data = _pdf("PO-123", "", "last-page-marker")
    options = ExtractionOptions(text_strategy="native_only")
    reader = PdfReader()
    result = await reader.read(PdfSource(data=data, filename="purchase.pdf"), options)
    repeated = await reader.read(PdfSource(data=data), options)

    assert result.document_id == hashlib.sha256(data).hexdigest()
    assert result.source_name == "purchase.pdf"
    assert result.page_count == 3
    assert [page.page_number for page in result.pages] == [1, 2, 3]
    assert "PO-123" in result.text and "last-page-marker" in result.text
    assert result.pages[1].text_blocks == ()
    assert result.pages[0].is_scanned is False
    assert all(not page.images for page in result.pages)
    assert result.pages[0].text_blocks[0].bbox is not None
    assert result.pages[0].text_blocks[0].block_id == repeated.pages[0].text_blocks[0].block_id


@pytest.mark.asyncio
async def test_ocr_strategy_retains_page_raster_and_digital_image_regions() -> None:
    result = await PdfReader().read(PdfSource(data=_image_pdf()), ExtractionOptions())

    assert result.pages[0].is_scanned is False
    assert result.pages[0].images[0].kind == "image"
    assert result.pages[0].images[0].bbox == (40.0, 100.0, 120.0, 160.0)
    scanned = result.pages[1]
    assert scanned.is_scanned is True
    assert [asset.kind for asset in scanned.images] == ["page"]
    raster = scanned.images[0]
    assert raster.page_number == 2
    assert raster.bbox == (0.0, 0.0, 400.0, 500.0)
    assert base64.b64decode(raster.data_base64).startswith(b"\x89PNG")


@pytest.mark.asyncio
async def test_multimodal_native_only_preserves_images_without_running_ocr() -> None:
    result = await PdfReader().read(
        PdfSource(data=_image_pdf()),
        ExtractionOptions(content_mode="multimodal", text_strategy="native_only"),
    )

    assert result.content_mode == "multimodal"
    assert result.pages[0].images[0].kind == "image"
    assert result.pages[1].images
    assert "PO-123" in result.text
    assert [page.images[-1].asset_id for page in result.pages] == ["p1-page", "p2-page"]


@pytest.mark.asyncio
@pytest.mark.parametrize("rotation", [90, 180, 270])
async def test_rotated_page_assets_and_evidence_use_displayed_pdf_coordinates(
    rotation: int,
) -> None:
    stream = io.BytesIO()
    Image.new("RGB", (40, 30), "blue").save(stream, format="PNG")
    with pymupdf.open() as document:
        page = document.new_page(width=400, height=500)
        page.insert_text((40, 60), "PO-123")
        page.insert_image(pymupdf.Rect(40, 100, 120, 160), stream=stream.getvalue())
        native_text_bbox = pymupdf.Rect(page.get_text("blocks")[0][:4])
        page.set_rotation(rotation)
        expected_text_bbox = tuple(native_text_bbox * page.rotation_matrix)
        expected_image_bbox = tuple(pymupdf.Rect(40, 100, 120, 160) * page.rotation_matrix)
        expected_page_bbox = tuple(page.rect)
        data = document.tobytes()

    result = await PdfReader().read(
        PdfSource(data=data),
        ExtractionOptions(content_mode="multimodal", text_strategy="native_only", render_dpi=72),
    )
    page = result.pages[0]
    assert page.text_blocks[0].bbox == pytest.approx(expected_text_bbox)
    image_asset = page.images[0]
    assert image_asset.bbox == pytest.approx(expected_image_bbox)
    assert image_asset.asset_id == "p1-image-1"
    assert page.images[-1].bbox == expected_page_bbox
    crop = Image.open(io.BytesIO(base64.b64decode(image_asset.data_base64)))
    red, green, blue = crop.getpixel((crop.width // 2, crop.height // 2))
    assert red < 10 and green < 10 and blue > 245


@pytest.mark.asyncio
async def test_rotated_table_bbox_uses_displayed_pdf_coordinates() -> None:
    with pymupdf.open() as document:
        page = document.new_page(width=400, height=500)
        for x in (40, 160, 280):
            page.draw_line((x, 80), (x, 160))
        for y in (80, 120, 160):
            page.draw_line((40, y), (280, y))
        page.insert_text((50, 100), "SKU")
        page.insert_text((170, 100), "Quantity")
        page.insert_text((50, 140), "SKU-1")
        page.insert_text((170, 140), "10")
        page.set_rotation(90)
        expected_bbox = tuple(pymupdf.Rect(40, 80, 280, 160) * page.rotation_matrix)
        data = document.tobytes()
    result = await PdfReader().read(
        PdfSource(data=data),
        ExtractionOptions(content_mode="multimodal", text_strategy="native_only"),
    )
    table = result.pages[0].tables[0]
    assert table.bbox == expected_bbox
    assert table.rows == (("SKU", "Quantity"), ("SKU-1", "10"))


@pytest.mark.asyncio
async def test_image_budget_is_cumulative_across_pages() -> None:
    stream = io.BytesIO()
    pixels = random.Random(123).randbytes(100 * 100 * 3)
    Image.frombytes("RGB", (100, 100), pixels).save(stream, format="PNG")
    with pymupdf.open() as document:
        for _ in range(2):
            page = document.new_page(width=100, height=100)
            page.insert_image(page.rect, stream=stream.getvalue())
        data = document.tobytes()
    with pytest.raises(ExtractionError) as caught:
        await PdfReader().read(
            PdfSource(data=data), ExtractionOptions(render_dpi=72, max_asset_bytes=50_000)
        )
    assert caught.value.code == "asset_limit_exceeded"


@pytest.mark.asyncio
async def test_selected_pages_keep_original_numbers_and_whole_selected_text() -> None:
    result = await PdfReader().read(
        PdfSource(data=_pdf("first", "second", "third")),
        ExtractionOptions(start_page=2, end_page=3, text_strategy="native_only"),
    )
    assert [page.page_number for page in result.pages] == [2, 3]
    assert "first" not in result.text
    assert "second" in result.text and "third" in result.text
    assert result.pages[0].text_blocks[0].page_number == 2


@pytest.mark.asyncio
async def test_native_table_cells_and_bbox_are_preserved() -> None:
    with pymupdf.open() as document:
        page = document.new_page(width=400, height=500)
        for x in (40, 160, 280):
            page.draw_line((x, 80), (x, 160))
        for y in (80, 120, 160):
            page.draw_line((40, y), (280, y))
        page.insert_text((50, 100), "SKU")
        page.insert_text((170, 100), "Quantity")
        page.insert_text((50, 140), "SKU-1")
        page.insert_text((170, 140), "10")
        data = document.tobytes()

    result = await PdfReader().read(
        PdfSource(data=data),
        ExtractionOptions(content_mode="multimodal", text_strategy="native_only"),
    )
    table = result.pages[0].tables[0]
    assert table.page_number == 1
    assert table.rows == (("SKU", "Quantity"), ("SKU-1", "10"))
    assert table.bbox == (40.0, 80.0, 280.0, 160.0)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("data", "options", "expected"),
    [
        (b"hello", ExtractionOptions(), "invalid_pdf"),
        (b"%PDF-1.7\ninvalid", ExtractionOptions(), "invalid_pdf"),
        (_pdf("hello"), ExtractionOptions(max_bytes=10), "input_too_large"),
        (_pdf("a", "b"), ExtractionOptions(end_page=3), "invalid_page_range"),
        (_pdf("a", "b"), ExtractionOptions(start_page=3), "invalid_page_range"),
        (_pdf("a", "b"), ExtractionOptions(max_pages=1), "page_limit_exceeded"),
        (_image_pdf(), ExtractionOptions(max_asset_bytes=10), "asset_limit_exceeded"),
    ],
)
async def test_failures_have_safe_stable_codes(
    data: bytes, options: ExtractionOptions, expected: str
) -> None:
    with pytest.raises(ExtractionError) as caught:
        await PdfReader().read(PdfSource(data=data), options)
    assert caught.value.code == expected
    assert "Traceback" not in str(caught.value)


@pytest.mark.asyncio
async def test_password_protected_pdf_is_rejected() -> None:
    with pymupdf.open() as document:
        document.new_page()
        data = document.tobytes(
            encryption=pymupdf.PDF_ENCRYPT_AES_256,
            owner_pw="owner-secret",
            user_pw="reader-secret",
        )
    with pytest.raises(ExtractionError) as caught:
        await PdfReader().read(PdfSource(data=data), ExtractionOptions())
    assert caught.value.code == "encrypted_pdf"
    assert "secret" not in str(caught.value)


@pytest.mark.asyncio
async def test_path_source_is_supported_and_missing_path_is_safe(tmp_path: Path) -> None:
    path = tmp_path / "native.pdf"
    path.write_bytes(_pdf("native text"))
    result = await PdfReader().read(
        PdfSource(path=path), ExtractionOptions(text_strategy="native_only")
    )
    assert result.source_name == "native.pdf"
    assert "native text" in result.text
    with pytest.raises(ExtractionError) as caught:
        await PdfReader().read(PdfSource(path=tmp_path / "missing.pdf"), ExtractionOptions())
    assert caught.value.code == "source_unavailable"
    assert str(tmp_path) not in str(caught.value)


@pytest.mark.asyncio
async def test_reader_dispatches_blocking_work_off_event_loop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import src.extraction.pdf_reader as reader_module

    entered = threading.Event()
    released = threading.Event()
    original = reader_module._read_sync
    event_loop_thread = threading.get_ident()
    worker_threads: list[int] = []

    def held_read(source: PdfSource, options: ExtractionOptions) -> DocumentResult:
        worker_threads.append(threading.get_ident())
        entered.set()
        if not released.wait(timeout=3):
            raise RuntimeError("Event loop failed to release the worker.")
        return original(source, options)

    monkeypatch.setattr(reader_module, "_read_sync", held_read)
    task = asyncio.create_task(
        PdfReader().read(PdfSource(data=_pdf("threaded")), ExtractionOptions())
    )
    try:
        for _ in range(100):
            if entered.is_set():
                break
            await asyncio.sleep(0.01)
        assert entered.is_set()
        assert worker_threads[0] != event_loop_thread
    finally:
        released.set()
    assert "threaded" in (await task).text


@pytest.mark.asyncio
async def test_pdf_normalization_is_serialized_across_reader_instances(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import src.extraction.pdf_reader as reader_module

    entered = threading.Event()
    released = threading.Event()
    counter_lock = threading.Lock()
    original = reader_module._read_sync
    active = 0
    peak = 0

    def tracked_read(source: PdfSource, options: ExtractionOptions) -> DocumentResult:
        nonlocal active, peak
        with counter_lock:
            active += 1
            peak = max(peak, active)
        entered.set()
        try:
            if not released.wait(timeout=3):
                raise RuntimeError("The test did not release PDF normalization.")
            return original(source, options)
        finally:
            with counter_lock:
                active -= 1

    monkeypatch.setattr(reader_module, "_read_sync", tracked_read)
    first = asyncio.create_task(
        PdfReader().read(PdfSource(data=_pdf("first")), ExtractionOptions())
    )
    second: asyncio.Task[DocumentResult] | None = None
    try:
        assert await asyncio.to_thread(entered.wait, 1)
        second = asyncio.create_task(
            PdfReader().read(PdfSource(data=_pdf("second")), ExtractionOptions())
        )
        await asyncio.sleep(0.05)
        assert peak == 1
    finally:
        released.set()
        await asyncio.gather(first, *([second] if second is not None else []))


@pytest.mark.asyncio
async def test_canceled_queued_pdf_is_not_normalized_after_lock_is_released(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import src.extraction.pdf_reader as reader_module

    entered = threading.Event()
    released = threading.Event()
    original = reader_module._read_sync
    calls: list[str] = []

    def held_read(source: PdfSource, options: ExtractionOptions) -> DocumentResult:
        calls.append(source.filename)
        entered.set()
        if not released.wait(timeout=3):
            raise RuntimeError("The test did not release PDF normalization.")
        return original(source, options)

    monkeypatch.setattr(reader_module, "_read_sync", held_read)
    first = asyncio.create_task(
        PdfReader().read(PdfSource(data=_pdf("first"), filename="first.pdf"), ExtractionOptions())
    )
    queued: asyncio.Task[DocumentResult] | None = None
    try:
        assert await asyncio.to_thread(entered.wait, 1)
        queued = asyncio.create_task(
            PdfReader().read(
                PdfSource(data=_pdf("queued"), filename="queued.pdf"), ExtractionOptions()
            )
        )
        await asyncio.sleep(0.05)
        queued.cancel()
        with pytest.raises(asyncio.CancelledError):
            await queued
    finally:
        released.set()
        await first
    await asyncio.sleep(0.05)
    assert calls == ["first.pdf"]
