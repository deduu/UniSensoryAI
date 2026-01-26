from enum import Enum
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, Optional

class DocumentType(Enum):
    PDF = "pdf"
    EXCEL = "excel"
    WORD = "word"
    POWERPOINT = "powerpoint"
    IMAGE = "image"
    WEB = "web"
    CODE = "code"
    UNKNOWN = "unknown"

@dataclass
class Document:
    """Represents a document to be processed."""
    id: str
    file_path: Path
    document_type: DocumentType
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
