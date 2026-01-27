from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, Any
from .base import BaseService
from ..db.models.document import Document
import uuid

class DocumentService(BaseService[Document]):
    def __init__(self, db: AsyncSession):
        super().__init__(db, Document)

    async def create_document(self, job_id: str, filename: str, content: dict) -> Document:
        """
        Save the processing result as a Document.
        """
        doc_id = str(uuid.uuid4())
        
        # Extract text and metadata from result
        # Assuming content is the dict returned by model.process
        extracted_text = content.get("content", content.get("text", ""))
        
        return await self.create(
            id=doc_id,
            job_id=job_id,
            filename=filename,
            content_text=extracted_text,
            content_chunks=content.get("chunks", []) # If model provides chunks
        )
