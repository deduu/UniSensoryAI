from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from fastapi.responses import JSONResponse
from pathlib import Path
from typing import Optional, Dict, Any
import tempfile
import json

from src.utils.config import ConfigLoader
from src.models import ModelLoader
from src.core.document import Document, DocumentType

app = FastAPI(
    title="UniSensoryAI Document Processing API",
    description="OpenAI-compatible API for multi-modal document understanding",
    version="0.1.0"
)

@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "healthy", "service": "UniSensoryAI"}

@app.post("/v1/process_document")
async def process_document(
    file: UploadFile = File(...),
    model_id: Optional[str] = Form("qwen3-vl-30b"),
    output_format: Optional[str] = Form("json")
) -> JSONResponse:
    """
    Process a document using the specified model.
    
    Args:
        file: Uploaded document file.
        model_id: Model to use for processing (default: qwen3-vl-30b).
        output_format: Output format - 'json' or 'markdown' (default: json).
        
    Returns:
        JSONResponse containing extracted content.
    """
    try:
        # Save uploaded file to temporary location
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename).suffix) as tmp_file:
            content = await file.read()
            tmp_file.write(content)
            tmp_path = Path(tmp_file.name)
        
        # Detect document type from extension
        ext = tmp_path.suffix.lower()
        doc_type_map = {
            ".pdf": DocumentType.PDF,
            ".xlsx": DocumentType.EXCEL,
            ".xls": DocumentType.EXCEL,
            ".docx": DocumentType.WORD,
            ".pptx": DocumentType.POWERPOINT,
            ".png": DocumentType.IMAGE,
            ".jpg": DocumentType.IMAGE,
            ".jpeg": DocumentType.IMAGE,
        }
        doc_type = doc_type_map.get(ext, DocumentType.UNKNOWN)
        
        # Create document object
        document = Document(
            id=file.filename,
            file_path=tmp_path,
            document_type=doc_type
        )
        
        # Load model
        model_config = ConfigLoader.get_model_config(model_id)
        model = ModelLoader.load_model(model_config)
        
        # Process Document
        # In a complete implementation, this would route to an agent. 
        # Here we directly call the model for testing purposes as requested.
        
        prompt = "Analyze this document and extract the whole content."
        processing_result = model.process(image=document.file_path, prompt=prompt)
        
        result = {
            "document_id": document.id,
            "document_type": doc_type.value,
            "model_used": model_id,
            "status": "success",
            "extracted_content": processing_result
        }
        
        # Cleanup
        model.unload()
        tmp_path.unlink()
        
        if output_format == "markdown":
            # Models return 'content' now, but checking 'text' for backward compat just in case
            extracted_text = result['extracted_content'].get('content', result['extracted_content'].get('text', ''))
            markdown_output = f"# {file.filename}\n\n{extracted_text}"
            return JSONResponse(content={"markdown": markdown_output})
        
        return JSONResponse(content=result)
        
    except Exception as e:
        import traceback
        import logging
        logger = logging.getLogger("uvicorn.error")
        logger.error(f"Error processing document request for model: {model_id}")
        logger.error(f"File: {file.filename if file else 'None'}")
        logger.error(f"Exception: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")

@app.post("/v1/chat/completions")
async def chat_completions(request: Dict[str, Any]) -> JSONResponse:
    """
    OpenAI-compatible chat completions endpoint (stub for compatibility).
    
    This is a minimal implementation to demonstrate OpenAI API compatibility.
    """
    messages = request.get("messages", [])
    model = request.get("model", "qwen3-vl-30b")
    
    # Mock response in OpenAI format
    response = {
        "id": "chatcmpl-mock-123",
        "object": "chat.completion",
        "created": 1234567890,
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "This is a mock response. Full implementation pending."
                },
                "finish_reason": "stop"
            }
        ],
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 20,
            "total_tokens": 30
        }
    }
    
    return JSONResponse(content=response)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8010)
