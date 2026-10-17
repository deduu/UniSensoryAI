"""Model-neutral queued PAPER processing, independent of HTTP and approval writes."""

import asyncio
import os
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any
from uuid import uuid4

import structlog

from src.extraction.contracts import ExtractionIssue, ExtractionOptions, PdfSource
from src.extraction.errors import ExtractionError
from src.extraction.service import ExtractionService
from src.ingestion.workflow_result import QueuedWorkflowResult
from src.paper.extraction_contracts import PaperExtractionParameters, PaperExtractionResult
from src.paper.schemas import get_paper_schema
from src.services.upload_storage import get_upload_directory, resolve_upload_path

logger = structlog.get_logger(__name__)
_INPUT_KEYS = frozenset(PaperExtractionParameters.model_fields)


def _store_artifact(result: PaperExtractionResult, root: Path) -> str:
    """Atomically save private output inside the deployment's upload directory."""
    root.mkdir(parents=True, exist_ok=True)
    artifact_name = f"{uuid4()}.paper-extraction.json"
    target = root / artifact_name
    temporary = root / f"{artifact_name}.tmp"
    try:
        temporary.write_text(result.model_dump_json(), encoding="utf-8")
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
    return artifact_name


class PaperExtractionProcessor:
    """Inject the host's shared extraction service into existing queue workers."""

    def __init__(
        self,
        service_factory: Callable[[], Awaitable[ExtractionService]],
        *,
        options: ExtractionOptions | None = None,
    ) -> None:
        """Receive a shared-service factory and validated deployment resource budgets.

        Args:
            service_factory: Lazy host factory that owns provider configuration.
            options: Immutable extraction settings; default document budget is 300 seconds.
        """
        self._service_factory = service_factory
        self._options = ExtractionOptions.model_validate(
            options if options is not None else ExtractionOptions()
        )

    async def process(self, file_path: str, metadata: dict[str, Any]) -> QueuedWorkflowResult:
        """Extract a PDF, then apply its external PAPER schema, retaining partial output.

        Args:
            file_path: Queued original PDF location beneath configured upload storage.
            metadata: Persisted validated schema and representation settings.

        Returns:
            Existing DocumentService-compatible content and a private artifact pointer.

        Raises:
            ExtractionError: Document acquisition failed; public errors contain no values.
        """
        parameters = PaperExtractionParameters.model_validate(
            {key: value for key, value in metadata.items() if key in _INPUT_KEYS}
        )
        path = await resolve_upload_path(file_path)
        try:
            service = await self._service_factory()
            options = ExtractionOptions.model_validate(
                {**self._options.model_dump(), "content_mode": parameters.content_mode}
            )
            document = await service.extract_document(
                PdfSource(path=path, filename=parameters.original_filename), options
            )
        except ExtractionError as error:
            logger.warning("paper_document_extraction_failed", error_code=error.code)
            raise ExtractionError(
                error.code, "Document extraction could not be completed."
            ) from None
        except Exception:  # noqa: BLE001 - provider failures must not expose private values
            logger.warning("paper_document_extraction_failed", error_code="extraction_unavailable")
            raise ExtractionError(
                "extraction_unavailable", "Document extraction is currently unavailable."
            ) from None

        warnings: tuple[ExtractionIssue, ...] = ()
        fields = None
        try:
            fields = await service.extract_fields(
                document,
                get_paper_schema(parameters.schema_name),
                model_profile=options.fields_profile,
                timeout_seconds=options.timeout_seconds,
            )
        except ExtractionError as error:
            warnings = (
                ExtractionIssue(
                    code=error.code,
                    message="Business fields could not be extracted. Review the retained document and enter or retry fields.",
                ),
            )
            logger.warning("paper_fields_incomplete", error_code=error.code)
        except Exception:  # noqa: BLE001 - retain OCR safely when a provider fails
            warnings = (
                ExtractionIssue(
                    code="field_extraction_failed",
                    message="Business fields could not be extracted. The document remains available for review.",
                ),
            )
            logger.warning("paper_fields_incomplete", error_code="field_extraction_failed")
        result = PaperExtractionResult(document=document, fields=fields, warnings=warnings)
        # Resolve the creator-owned directory before writing. A cancelled caller
        # must wait for its thread and remove output before the worker hands off.
        artifact_root = await asyncio.to_thread(get_upload_directory().resolve)
        write_task = asyncio.create_task(asyncio.to_thread(_store_artifact, result, artifact_root))
        try:
            artifact_name = await asyncio.shield(write_task)
        except asyncio.CancelledError:
            try:
                artifact_name = await write_task
                await asyncio.to_thread((artifact_root / artifact_name).unlink, missing_ok=True)
            except Exception:  # noqa: BLE001 - do not replace the original cancellation
                logger.warning("cancelled_workflow_artifact_cleanup_failed")
            raise
        warning_count = (
            len(document.warnings) + len(warnings) + (len(fields.warnings) if fields else 0)
        )
        model_ids = list(
            dict.fromkeys(
                identity
                for identity in document.model_ids
                + (fields.model_ids if fields is not None else ())
                if identity.strip()
            )
        )
        artifact_path = artifact_root / artifact_name

        async def discard_artifact() -> None:
            # Capture the creator's resolved path, never a caller-mutated chunk pointer.
            await asyncio.to_thread(artifact_path.unlink, missing_ok=True)

        return QueuedWorkflowResult(
            {
                "content": document.text,
                "chunks": [
                    {
                        "type": "paper_extraction_artifact",
                        "version": "1",
                        "artifact_name": artifact_name,
                    }
                ],
                "job_metadata": {
                    "model_ids": model_ids,
                    **({"model_id": model_ids[0]} if len(model_ids) == 1 else {}),
                    "page_count": document.page_count,
                    "warning_count": warning_count,
                    "extraction_status": result.status,
                },
            },
            discard=discard_artifact,
        )
