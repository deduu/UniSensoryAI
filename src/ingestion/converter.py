import fitz  # PyMuPDF
from pathlib import Path
from typing import List, Union, Any
import logging
from PIL import Image
import io

# Optional imports for Office files
try:
    import docx
except ImportError:
    docx = None

try:
    import pptx
except ImportError:
    pptx = None

try:
    import openpyxl
except ImportError:
    openpyxl = None

logger = logging.getLogger(__name__)


class DocumentConverter:
    """
    Handles conversion of various document formats to images or text for processing.
    """

    @staticmethod
    def get_supported_extensions() -> List[str]:
        return [
            ".pdf",
            ".png",
            ".jpg",
            ".jpeg",
            ".bmp",
            ".tiff",
            ".webp",
            ".docx",
            ".pptx",
            ".xlsx",
        ]

    @staticmethod
    def convert(file_path: Union[str, Path]) -> List[Any]:
        """
        Convert a document to a list of content chunks.
        - For Images/PDF: Returns list of PIL Images.
        - For Office Files: Returns list of strings (text content).
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        ext = path.suffix.lower()

        # 1. Image Formats
        if ext in [".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".webp"]:
            return [Image.open(path)]

        # 2. PDF (Visual)
        if ext == ".pdf":
            return DocumentConverter._convert_pdf(path)

        # 3. Office Formats (Text)
        if ext == ".docx":
            return DocumentConverter._extract_docx(path)
        if ext == ".pptx":
            return DocumentConverter._extract_pptx(path)
        if ext == ".xlsx":
            return DocumentConverter._extract_xlsx(path)

        raise ValueError(f"Unsupported file format: {ext}")

    @staticmethod
    def _convert_pdf(path: Path, zoom: int = 2) -> List[Image.Image]:
        """Render PDF pages as images."""
        logger.info(f"Converting PDF {path.name} to images...")
        images = []
        try:
            doc = fitz.open(path)
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                mat = fitz.Matrix(zoom, zoom)
                pix = page.get_pixmap(matrix=mat)
                img = Image.open(io.BytesIO(pix.tobytes("png")))
                images.append(img)
            doc.close()
            return images
        except Exception as e:
            logger.error(f"Failed to convert PDF {path}: {e}")
            raise

    @staticmethod
    def _extract_docx(path: Path) -> List[str]:
        """Extract text from DOCX."""
        if not docx:
            raise ImportError(
                "python-docx is installed but failed to import. Please check environment."
            )

        logger.info(f"Extracting text from DOCX {path.name}...")
        try:
            doc = docx.Document(path)
            full_text = []
            for para in doc.paragraphs:
                if para.text.strip():
                    full_text.append(para.text)
            return ["\n".join(full_text)] if full_text else []
        except Exception as e:
            logger.error(f"Failed to parse DOCX {path}: {e}")
            raise

    @staticmethod
    def _extract_pptx(path: Path) -> List[str]:
        """Extract text from PPTX (one string per slide)."""
        if not pptx:
            raise ImportError("python-pptx is installed but failed to import.")

        logger.info(f"Extracting text from PPTX {path.name}...")
        try:
            prs = pptx.Presentation(path)
            slides_text = []
            for i, slide in enumerate(prs.slides):
                text_runs = []
                for shape in slide.shapes:
                    if hasattr(shape, "text") and shape.text:
                        text_runs.append(shape.text)

                if text_runs:
                    slides_text.append(f"Slide {i+1}:\n" + "\n".join(text_runs))
            return slides_text
        except Exception as e:
            logger.error(f"Failed to parse PPTX {path}: {e}")
            raise

    @staticmethod
    def _extract_xlsx(path: Path) -> List[str]:
        """Extract text from XLSX (one string per sheet)."""
        if not openpyxl:
            raise ImportError("openpyxl is installed but failed to import.")

        logger.info(f"Extracting text from XLSX {path.name}...")
        try:
            wb = openpyxl.load_workbook(path, data_only=True)
            sheets_text = []
            for sheetname in wb.sheetnames:
                sheet = wb[sheetname]
                rows = []
                for row in sheet.iter_rows(values_only=True):
                    # Filter None
                    row_text = [str(cell) for cell in row if cell is not None]
                    if row_text:
                        rows.append(" | ".join(row_text))

                if rows:
                    sheets_text.append(f"Sheet '{sheetname}':\n" + "\n".join(rows))
            return sheets_text
        except Exception as e:
            logger.error(f"Failed to parse XLSX {path}: {e}")
            raise
