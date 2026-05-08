import fitz  # PyMuPDF
from pathlib import Path
from typing import List, Union, Any, Optional
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


def _esc(text: str) -> str:
    """Escape HTML special characters."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


_HTML_BASE_STYLE = (
    "body{font-family:Georgia,serif;max-width:760px;margin:2rem auto;"
    "padding:0 1.5rem;color:#1a1a1a;line-height:1.75;font-size:15px}"
    "h1,h2,h3,h4{margin:1.4em 0 .4em;font-weight:700}"
    "h1{font-size:1.7em}h2{font-size:1.35em}h3{font-size:1.1em}"
    "p{margin:.5em 0}li{margin:.2em 0}"
    "table{border-collapse:collapse;width:100%;margin:1em 0}"
    "td,th{border:1px solid #ccc;padding:.35em .6em;text-align:left}"
    "th{background:#f4f4f4;font-weight:600}"
)

_XLSX_STYLE = (
    "body{font-family:system-ui,sans-serif;margin:0;padding:1rem;color:#1a1a1a;font-size:13px}"
    "h2{font-size:.85em;font-weight:700;text-transform:uppercase;letter-spacing:.06em;"
    "color:#6b7280;margin:1.5rem 0 .4rem}"
    "table{border-collapse:collapse;width:100%;margin-bottom:1.5rem}"
    "td,th{border:1px solid #d1d5db;padding:.3em .55em;white-space:pre}"
    "th{background:#f3f4f6;font-weight:600}"
    "tr:nth-child(even) td{background:#f9fafb}"
)

_PPTX_STYLE = (
    "body{font-family:system-ui,sans-serif;margin:0;padding:1rem;color:#1a1a1a;font-size:14px}"
    ".slide{border:1px solid #e5e7eb;border-radius:8px;padding:1.25rem 1.5rem;margin-bottom:1.25rem}"
    ".slide-num{font-size:.7em;font-weight:700;text-transform:uppercase;letter-spacing:.08em;"
    "color:#9ca3af;margin-bottom:.6rem}"
    "p{margin:.25em 0}"
)


class DocumentConverter:
    """
    Handles conversion of various document formats to images or text for processing.
    Supports optional page range selection via start_page and end_page (1-indexed, inclusive).
    """

    @staticmethod
    def to_html(file_path: Union[str, Path]) -> str:
        """Convert an Office document to an HTML string for browser preview.

        Supports .docx, .xlsx, and .pptx. Raises ValueError for other extensions.
        """
        path = Path(file_path)
        ext = path.suffix.lower()
        if ext == ".docx":
            return DocumentConverter._docx_to_html(path)
        if ext == ".xlsx":
            return DocumentConverter._xlsx_to_html(path)
        if ext == ".pptx":
            return DocumentConverter._pptx_to_html(path)
        raise ValueError(f"HTML preview not supported for {ext}")

    @staticmethod
    def _docx_to_html(path: Path) -> str:
        if not docx:
            raise ImportError("python-docx is not available.")
        doc = docx.Document(path)
        parts = [f'<!DOCTYPE html><html><head><meta charset="utf-8"><style>{_HTML_BASE_STYLE}</style></head><body>']
        for para in doc.paragraphs:
            style = para.style.name
            text = para.text
            if not text.strip():
                parts.append("<br>")
                continue
            safe = _esc(text)
            if "Heading 1" in style:
                parts.append(f"<h1>{safe}</h1>")
            elif "Heading 2" in style:
                parts.append(f"<h2>{safe}</h2>")
            elif "Heading 3" in style:
                parts.append(f"<h3>{safe}</h3>")
            elif any(f"Heading {n}" in style for n in ("4", "5", "6")):
                parts.append(f"<h4>{safe}</h4>")
            elif "List" in style:
                parts.append(f"<li>{safe}</li>")
            else:
                parts.append(f"<p>{safe}</p>")
        for table in doc.tables:
            parts.append("<table>")
            for i, row in enumerate(table.rows):
                tag = "th" if i == 0 else "td"
                parts.append("<tr>" + "".join(f"<{tag}>{_esc(cell.text)}</{tag}>" for cell in row.cells) + "</tr>")
            parts.append("</table>")
        parts.append("</body></html>")
        return "\n".join(parts)

    @staticmethod
    def _xlsx_to_html(path: Path) -> str:
        if not openpyxl:
            raise ImportError("openpyxl is not available.")
        wb = openpyxl.load_workbook(path, data_only=True)
        parts = [f'<!DOCTYPE html><html><head><meta charset="utf-8"><style>{_XLSX_STYLE}</style></head><body>']
        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            rows = [r for r in ws.iter_rows(values_only=True) if any(c is not None for c in r)]
            if not rows:
                continue
            parts.append(f"<h2>{_esc(sheet_name)}</h2><table>")
            for i, row in enumerate(rows):
                tag = "th" if i == 0 else "td"
                parts.append(
                    "<tr>"
                    + "".join(f"<{tag}>{_esc(str(c)) if c is not None else ''}</{tag}>" for c in row)
                    + "</tr>"
                )
            parts.append("</table>")
        parts.append("</body></html>")
        return "\n".join(parts)

    @staticmethod
    def _pptx_to_html(path: Path) -> str:
        if not pptx:
            raise ImportError("python-pptx is not available.")
        prs = pptx.Presentation(path)
        parts = [f'<!DOCTYPE html><html><head><meta charset="utf-8"><style>{_PPTX_STYLE}</style></head><body>']
        for i, slide in enumerate(prs.slides):
            texts = [shape.text for shape in slide.shapes if hasattr(shape, "text") and shape.text.strip()]
            if not texts:
                continue
            parts.append(f'<div class="slide"><div class="slide-num">Slide {i + 1}</div>')
            for text in texts:
                for line in _esc(text).split("\n"):
                    if line.strip():
                        parts.append(f"<p>{line}</p>")
            parts.append("</div>")
        parts.append("</body></html>")
        return "\n".join(parts)

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
    def convert(
        file_path: Union[str, Path],
        start_page: Optional[int] = None,
        end_page: Optional[int] = None,
    ) -> List[Any]:
        """
        Convert a document to a list of content chunks.
        - For Images/PDF: Returns list of PIL Images.
        - For Office Files: Returns list of strings (text content).

        Args:
            file_path: Path to the document file.
            start_page: Optional 1-indexed start page (inclusive).
            end_page: Optional 1-indexed end page (inclusive).
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        ext = path.suffix.lower()

        # 1. Image Formats (single page — page range is ignored)
        if ext in [".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".webp"]:
            return [Image.open(path)]

        # 2. PDF (Visual)
        if ext == ".pdf":
            return DocumentConverter._convert_pdf(path, start_page=start_page, end_page=end_page)

        # 3. Office Formats (Text)
        if ext == ".docx":
            return DocumentConverter._extract_docx(path)
        if ext == ".pptx":
            return DocumentConverter._extract_pptx(path, start_page=start_page, end_page=end_page)
        if ext == ".xlsx":
            return DocumentConverter._extract_xlsx(path, start_page=start_page, end_page=end_page)

        raise ValueError(f"Unsupported file format: {ext}")

    @staticmethod
    def _resolve_page_range(
        total: int,
        start_page: Optional[int],
        end_page: Optional[int],
        item_label: str = "page",
    ) -> tuple[int, int]:
        """
        Resolve 1-indexed start/end into 0-indexed (start_idx, end_idx) for use
        with range(start_idx, end_idx).

        Raises ValueError if start_page exceeds total items.
        Caps end_page to total items if it exceeds the document length.

        Args:
            total: Total number of items in the document.
            start_page: Optional 1-indexed start (inclusive).
            end_page: Optional 1-indexed end (inclusive).
            item_label: Label for error messages (e.g. "page", "slide", "sheet").

        Returns:
            Tuple of (start_idx, end_idx) for use with range().
        """
        start_idx = 0
        end_idx = total

        if start_page is not None:
            if start_page > total:
                raise ValueError(
                    f"Requested start {item_label} {start_page} exceeds document "
                    f"length of {total} {item_label}(s)."
                )
            start_idx = start_page - 1

        if end_page is not None:
            # Gracefully cap to total if end_page exceeds document length
            end_idx = min(end_page, total)

        return start_idx, end_idx

    @staticmethod
    def _convert_pdf(
        path: Path,
        zoom: int = 2,
        start_page: Optional[int] = None,
        end_page: Optional[int] = None,
    ) -> List[Image.Image]:
        """Render PDF pages as images, optionally filtering by page range."""
        logger.info(f"Converting PDF {path.name} to images...")
        images = []
        try:
            doc = fitz.open(path)
            total_pages = len(doc)
            start_idx, end_idx = DocumentConverter._resolve_page_range(
                total_pages, start_page, end_page, item_label="page"
            )
            logger.info(
                f"Processing pages {start_idx + 1}–{end_idx} of {total_pages} total."
            )

            for page_num in range(start_idx, end_idx):
                page = doc.load_page(page_num)
                mat = fitz.Matrix(zoom, zoom)
                pix = page.get_pixmap(matrix=mat)
                img = Image.open(io.BytesIO(pix.tobytes("png")))
                images.append(img)
            doc.close()
            return images
        except ValueError:
            # Re-raise validation errors without wrapping
            raise
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
            for table in doc.tables:
                for row in table.rows:
                    cells = [
                        cell.text.strip()
                        for cell in row.cells
                        if cell.text and cell.text.strip()
                    ]
                    if cells:
                        full_text.append(" | ".join(cells))
            return ["\n".join(full_text)] if full_text else []
        except Exception as e:
            logger.error(f"Failed to parse DOCX {path}: {e}")
            raise

    @staticmethod
    def _extract_pptx(
        path: Path,
        start_page: Optional[int] = None,
        end_page: Optional[int] = None,
    ) -> List[str]:
        """Extract text from PPTX (one string per slide), optionally filtering by slide range."""
        if not pptx:
            raise ImportError("python-pptx is installed but failed to import.")

        logger.info(f"Extracting text from PPTX {path.name}...")
        try:
            prs = pptx.Presentation(path)
            all_slides = list(prs.slides)
            total_slides = len(all_slides)
            start_idx, end_idx = DocumentConverter._resolve_page_range(
                total_slides, start_page, end_page, item_label="slide"
            )
            logger.info(
                f"Processing slides {start_idx + 1}–{end_idx} of {total_slides} total."
            )

            slides_text = []
            for i in range(start_idx, end_idx):
                slide = all_slides[i]
                text_runs = []
                for shape in slide.shapes:
                    if hasattr(shape, "text") and shape.text:
                        text_runs.append(shape.text)

                if text_runs:
                    slides_text.append(f"Slide {i+1}:\n" + "\n".join(text_runs))
            return slides_text
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Failed to parse PPTX {path}: {e}")
            raise

    @staticmethod
    def _extract_xlsx(
        path: Path,
        start_page: Optional[int] = None,
        end_page: Optional[int] = None,
    ) -> List[str]:
        """Extract text from XLSX (one string per sheet), optionally filtering by sheet range."""
        if not openpyxl:
            raise ImportError("openpyxl is installed but failed to import.")

        logger.info(f"Extracting text from XLSX {path.name}...")
        try:
            wb = openpyxl.load_workbook(path, data_only=True)
            all_sheetnames = wb.sheetnames
            total_sheets = len(all_sheetnames)
            start_idx, end_idx = DocumentConverter._resolve_page_range(
                total_sheets, start_page, end_page, item_label="sheet"
            )
            logger.info(
                f"Processing sheets {start_idx + 1}–{end_idx} of {total_sheets} total."
            )

            sheets_text = []
            for i in range(start_idx, end_idx):
                sheetname = all_sheetnames[i]
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
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Failed to parse XLSX {path}: {e}")
            raise

