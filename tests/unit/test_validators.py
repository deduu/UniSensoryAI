"""Tests for src/api/validators.py — upload validation."""

import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from io import BytesIO

# Mock heavy ML modules before importing
_MOCK_MODULES = [
    "torch", "torch.cuda", "torch.nn", "torch.nn.functional",
    "torchvision", "torchvision.transforms",
    "transformers", "accelerate", "bitsandbytes",
    "nvitop",
    "fitz", "pymupdf", "pymupdf.extra", "pymupdf._extra",
]
for mod in _MOCK_MODULES:
    if mod not in sys.modules:
        sys.modules[mod] = MagicMock()

from fastapi import HTTPException
from src.api.validators import UploadValidator


def _make_upload(filename: str, content: bytes = b"fake content") -> MagicMock:
    """Create a mock UploadFile."""
    mock = AsyncMock()
    mock.filename = filename
    mock.size = len(content)
    mock.read = AsyncMock(return_value=content)
    mock.seek = AsyncMock()
    return mock


class TestUploadValidator:
    @pytest.mark.asyncio
    async def test_accepts_valid_pdf(self):
        """Valid PDF should pass validation."""
        upload = _make_upload("document.pdf", b"%PDF-1.4 content")
        # Should not raise
        await UploadValidator.validate(upload)

    @pytest.mark.asyncio
    async def test_accepts_valid_image(self):
        """Valid image should pass validation."""
        upload = _make_upload("photo.png", b"\x89PNG")
        await UploadValidator.validate(upload)

    @pytest.mark.asyncio
    async def test_accepts_valid_docx(self):
        """Valid DOCX should pass validation."""
        upload = _make_upload("report.docx", b"PK content")
        await UploadValidator.validate(upload)

    @pytest.mark.asyncio
    async def test_rejects_blocked_extension(self):
        """Blocked extension (.exe) should return 400."""
        upload = _make_upload("malware.exe", b"MZ content")
        with pytest.raises(HTTPException) as exc_info:
            await UploadValidator.validate(upload)
        assert exc_info.value.status_code == 400
        assert "not allowed" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_rejects_unsupported_extension(self):
        """Unsupported extension should return 415."""
        upload = _make_upload("data.csv", b"a,b,c")
        with pytest.raises(HTTPException) as exc_info:
            await UploadValidator.validate(upload)
        assert exc_info.value.status_code == 415
        assert "Unsupported" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_rejects_oversized_file(self):
        """File exceeding MAX_FILE_SIZE should return 413."""
        upload = _make_upload("big.pdf", b"x")
        upload.size = 200 * 1024 * 1024  # 200 MB
        with pytest.raises(HTTPException) as exc_info:
            await UploadValidator.validate(upload)
        assert exc_info.value.status_code == 413
        assert "too large" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_rejects_empty_file(self):
        """Empty file should return 400."""
        upload = _make_upload("empty.pdf", b"")
        upload.size = 0
        with pytest.raises(HTTPException) as exc_info:
            await UploadValidator.validate(upload)
        assert exc_info.value.status_code == 400
        assert "Empty" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_rejects_missing_filename(self):
        """Missing filename should return 400."""
        upload = _make_upload("", b"content")
        upload.filename = ""
        with pytest.raises(HTTPException) as exc_info:
            await UploadValidator.validate(upload)
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_rejects_bat_extension(self):
        """Blocked .bat should return 400."""
        upload = _make_upload("script.bat", b"echo hello")
        with pytest.raises(HTTPException) as exc_info:
            await UploadValidator.validate(upload)
        assert exc_info.value.status_code == 400
