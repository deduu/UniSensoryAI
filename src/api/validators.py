"""Upload file validation — size limits, extension checks, safety."""

import logging
from pathlib import Path
from typing import Set

from fastapi import HTTPException, UploadFile

logger = logging.getLogger(__name__)


class UploadValidator:
    """Validates uploaded files at the API boundary.

    Enforces file size limits, extension allowlisting, and blocks
    known dangerous extensions before the file reaches the queue.

    Attributes:
        MAX_FILE_SIZE: Maximum file size in bytes (default 100 MB).
        ALLOWED_EXTENSIONS: Set of permitted file extensions.
        BLOCKED_EXTENSIONS: Set of explicitly blocked dangerous extensions.
    """

    MAX_FILE_SIZE: int = 100 * 1024 * 1024  # 100 MB

    ALLOWED_EXTENSIONS: Set[str] = {
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
    }

    BLOCKED_EXTENSIONS: Set[str] = {
        ".exe",
        ".bat",
        ".sh",
        ".ps1",
        ".cmd",
        ".dll",
        ".so",
        ".msi",
        ".scr",
        ".com",
        ".vbs",
        ".js",
        ".jar",
    }

    @classmethod
    async def validate(cls, file: UploadFile) -> None:
        """Validate an uploaded file.

        Checks:
        1. Filename is present.
        2. Extension is not blocked.
        3. Extension is in the allow list.
        4. File size does not exceed the limit.

        Args:
            file: FastAPI UploadFile to validate.

        Raises:
            HTTPException: 400 if filename missing or extension blocked.
            HTTPException: 415 if extension not in allow list.
            HTTPException: 413 if file exceeds size limit.
        """
        # 1. Filename check
        if not file.filename:
            raise HTTPException(status_code=400, detail="Filename is required.")

        ext = Path(file.filename).suffix.lower()

        # 2. Blocked extension check
        if ext in cls.BLOCKED_EXTENSIONS:
            logger.warning("Blocked upload attempt: %s", file.filename)
            raise HTTPException(
                status_code=400,
                detail=f"File type '{ext}' is not allowed for security reasons.",
            )

        # 3. Allowed extension check
        if ext not in cls.ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=415,
                detail=(
                    f"Unsupported file type '{ext}'. "
                    f"Supported: {sorted(cls.ALLOWED_EXTENSIONS)}"
                ),
            )

        # 4. File size check (read content length from headers or seek)
        # UploadFile may have a size attribute or we check via seek
        file_size = 0
        if hasattr(file, "size") and file.size is not None:
            file_size = file.size
        else:
            # Read to determine size, then seek back
            content = await file.read()
            file_size = len(content)
            await file.seek(0)

        if file_size == 0:
            raise HTTPException(status_code=400, detail="Empty file uploaded.")

        if file_size > cls.MAX_FILE_SIZE:
            size_mb = file_size / (1024 * 1024)
            max_mb = cls.MAX_FILE_SIZE / (1024 * 1024)
            raise HTTPException(
                status_code=413,
                detail=(
                    f"File too large ({size_mb:.1f} MB). "
                    f"Maximum allowed: {max_mb:.0f} MB."
                ),
            )

        logger.info(
            "Upload validated: file=%s, ext=%s, size=%d bytes",
            file.filename,
            ext,
            file_size,
        )
