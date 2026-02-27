"""Tests for src/ingestion/converter.py — DocumentConverter format handling."""

import pytest
from PIL import Image
from src.ingestion.converter import DocumentConverter


class TestImageConversion:
    def test_convert_png(self, sample_image):
        """PNG image should return a list with one PIL Image."""
        result = DocumentConverter.convert(sample_image)
        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], Image.Image)

    def test_convert_jpg(self, tmp_path):
        """JPEG image should return a list with one PIL Image."""
        img = Image.new("RGB", (10, 10), "green")
        jpg_path = tmp_path / "test.jpg"
        img.save(jpg_path)

        result = DocumentConverter.convert(jpg_path)
        assert len(result) == 1
        assert isinstance(result[0], Image.Image)


class TestPdfConversion:
    def test_convert_pdf(self, sample_pdf):
        """PDF should return a list of PIL Images (one per page)."""
        result = DocumentConverter.convert(sample_pdf)
        assert isinstance(result, list)
        assert len(result) >= 1
        assert isinstance(result[0], Image.Image)


class TestOfficeConversion:
    def test_convert_docx(self, sample_docx):
        """DOCX should return a list of strings."""
        result = DocumentConverter.convert(sample_docx)
        assert isinstance(result, list)
        assert len(result) >= 1
        assert isinstance(result[0], str)
        assert "Test paragraph" in result[0]

    def test_convert_pptx(self, sample_pptx):
        """PPTX should return a list of strings (one per slide)."""
        result = DocumentConverter.convert(sample_pptx)
        assert isinstance(result, list)
        assert len(result) >= 1
        assert isinstance(result[0], str)
        assert "Test Slide Title" in result[0]

    def test_convert_xlsx(self, sample_xlsx):
        """XLSX should return a list of strings (one per sheet)."""
        result = DocumentConverter.convert(sample_xlsx)
        assert isinstance(result, list)
        assert len(result) >= 1
        assert isinstance(result[0], str)
        assert "Header1" in result[0]


class TestEdgeCases:
    def test_unsupported_format(self, tmp_path):
        """Unsupported file extension should raise ValueError."""
        bad_file = tmp_path / "test.xyz"
        bad_file.write_text("content")
        with pytest.raises(ValueError, match="Unsupported"):
            DocumentConverter.convert(bad_file)

    def test_file_not_found(self):
        """Non-existent file should raise FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            DocumentConverter.convert("/nonexistent/path/file.pdf")

    def test_supported_extensions(self):
        """get_supported_extensions should return expected list."""
        exts = DocumentConverter.get_supported_extensions()
        assert ".pdf" in exts
        assert ".png" in exts
        assert ".docx" in exts
        assert ".xlsx" in exts
        assert ".pptx" in exts
