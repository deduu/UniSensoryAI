"""Retained-source provenance without assigning old OCR cost to a new extraction."""

from typing import Annotated, Literal

from pydantic import StringConstraints

from src.extraction.contracts.base import _Contract


class DocumentReuse(_Contract):
    """An exact verified OCR snapshot reused for independent canonical field passes."""

    source_job_id: Annotated[
        str,
        StringConstraints(strict=True, min_length=1, max_length=50, pattern=r"^[A-Za-z0-9-]+$"),
    ]
    source_sha256: Annotated[
        str, StringConstraints(strict=True, min_length=64, max_length=64, pattern=r"^[a-f0-9]{64}$")
    ]
    mode: Literal["retained_verified_ocr"]
