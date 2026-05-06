"""Document processor — orchestrates document processing via the pipeline engine.

This module provides:
- ``get_cached_model``: Thread-safe model cache lookup/load.
- ``process_document_job``: Entry point called by the ingestion queue worker.

The processor delegates to :class:`PipelineExecutor` for the actual
processing flow, keeping this module as a thin adapter between the
queue layer and the pipeline engine.
"""

import logging
from pathlib import Path
from typing import Any, Dict, Optional

from src.models.cache import ModelCacheManager

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Model Cache — uses ModelCacheManager with LRU eviction + OOM protection
# ---------------------------------------------------------------------------

_model_cache = ModelCacheManager(max_models=3)


async def get_cached_model(
    model_id: str, api_keys: Optional[Dict[str, str]] = None
) -> Any:
    """Retrieve model from cache or load it if not present.

    Thin wrapper around :class:`ModelCacheManager.get_or_load` that
    preserves the function signature for backward compatibility.

    Args:
        model_id: Model identifier as defined in models.yaml.
        api_keys: Optional API key overrides for cloud models.

    Returns:
        Loaded model instance.

    Raises:
        RuntimeError: If model loading fails.
    """
    return await _model_cache.get_or_load(model_id, api_keys)


# ---------------------------------------------------------------------------
# Document Processing Entry Point
# ---------------------------------------------------------------------------


async def process_document_job(
    file_path: str,
    model_id: str = "qwen2-vl-2b-instruct",
    api_keys: Optional[Dict[str, str]] = None,
    start_page: Optional[int] = None,
    end_page: Optional[int] = None,
) -> dict:
    """Background task to process a document via the pipeline engine.

    This function is the entry point called by :class:`IngestionQueue`.
    It builds a :class:`PipelineContext`, runs the ``basic`` pipeline,
    and returns the formatted output dict.

    The function signature is intentionally unchanged from the original
    monolithic implementation to preserve backward compatibility with
    the queue worker and all existing tests.

    Args:
        file_path: Path to the document file.
        model_id: Model identifier to use for processing.
        api_keys: Optional dictionary of API keys to override env vars.
        start_page: Optional 1-indexed start page (inclusive).
        end_page: Optional 1-indexed end page (inclusive).

    Returns:
        Dict with ``content`` and ``page_count`` on success,
        or ``error`` key on failure.
    """
    try:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        logger.info("Starting processing for file: %s", file_path)

        # Import here to avoid circular imports at module level
        from src.pipeline import PipelineContext, PipelineExecutor

        context = PipelineContext(
            file_path=path,
            model_id=model_id,
            api_keys=api_keys,
            start_page=start_page,
            end_page=end_page,
        )

        executor = PipelineExecutor(pipeline_name="basic")
        result_ctx = await executor.execute(context)

        if result_ctx.formatted_output:
            logger.info("Processing complete for %s", file_path)
            return result_ctx.formatted_output

        return {"error": "Pipeline produced no output."}

    except FileNotFoundError:
        raise
    except Exception as e:
        # Catch pipeline/conversion errors and return error dict
        # to match original behavior (some errors returned as dict, some raised)
        error_msg = str(e)
        if "conversion" in error_msg.lower() or "no processable" in error_msg.lower():
            return {"error": f"Document conversion failed: {error_msg}"}
        logger.error("Failed to process document %s: %s", file_path, e, exc_info=True)
        raise
