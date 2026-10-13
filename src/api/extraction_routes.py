"""Authenticated, non-persisting API adapter for the reusable extraction service."""

import asyncio
import json
import os
from collections.abc import Callable, Coroutine
from pathlib import Path, PurePosixPath
from typing import Annotated, Any, cast

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from starlette.responses import Response

from src.api.auth import UserContext, get_user_context
from src.api.rate_limit import InProcessRateLimiter, RateLimitDep
from src.extraction.contracts import (
    DocumentResult,
    ExternalSchema,
    ExtractionOptions,
    ExtractionResult,
    FieldExtractionResult,
    PdfSource,
)
from src.extraction.errors import ExtractionError
from src.extraction.service import ExtractionService

_MAX_UPLOAD_BYTES = 100 * 1024 * 1024
_READ_CHUNK_BYTES = 1024 * 1024
_MAX_OPTIONS_BYTES = 16 * 1024
_MAX_SCHEMA_BYTES = 128 * 1024
_SERVER_OPTIONS = ExtractionOptions()
_limiter = InProcessRateLimiter(requests_per_minute=6000, burst=100)
_rate_limit = RateLimitDep(requests_per_minute=6000, limiter=_limiter)


def _input_error(code: str = "invalid_request") -> HTTPException:
    return HTTPException(
        status_code=422,
        detail={"code": code, "message": "Extraction inputs are invalid."},
    )


class _SafeValidationRoute(APIRoute):
    def get_route_handler(self) -> Callable[[Request], Coroutine[Any, Any, Response]]:
        """Prevent validation responses from echoing document or credential values."""
        handler = super().get_route_handler()

        async def safe_handler(request: Request) -> Response:
            try:
                return await handler(request)
            except RequestValidationError:
                raise _input_error() from None

        return safe_handler


router = APIRouter(route_class=_SafeValidationRoute, tags=["extraction"])


def _external_schema(value: Any) -> ExternalSchema:
    if not isinstance(value, dict):
        # Pydantic v2 converts ValueError, but not TypeError, into input validation.
        raise ValueError("The external schema must be a JSON object.")  # noqa: TRY004
    if "json_schema" in value:
        return ExternalSchema.model_validate(value)
    return ExternalSchema(json_schema=value)


class _FieldsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    document: DocumentResult
    external_schema: ExternalSchema = Field(alias="schema")
    model_profile: str = Field(default="fields", min_length=1, max_length=128)
    timeout_seconds: float = Field(default=300, gt=0, le=300)

    @field_validator("external_schema", mode="before")
    @classmethod
    def validate_schema(cls, value: Any) -> ExternalSchema:
        """Accept a versioned envelope or a raw business JSON Schema."""
        return _external_schema(value)


async def build_extraction_service(config_path: str | None = None) -> ExtractionService:
    """Load the composition root lazily to keep API imports model-free.

    Args:
        config_path: Optional host-configured extraction YAML location.

    Returns:
        Configured service whose lifetime belongs to the hosting application.
    """
    from src.extraction.composition import build_extraction_service as factory

    return await factory(config_path=Path(config_path) if config_path else None)


async def get_extraction_service(request: Request) -> ExtractionService:
    """Reuse an injected service or lazily construct one per application.

    Args:
        request: Request identifying the hosting application.

    Returns:
        The application's extraction service.

    Raises:
        HTTPException: Host configuration cannot construct an extraction service.
    """
    existing = getattr(request.app.state, "extraction_service", None)
    if existing is not None:
        return cast(ExtractionService, existing)
    lock = getattr(request.app.state, "extraction_service_lock", None)
    if lock is None:
        lock = asyncio.Lock()
        request.app.state.extraction_service_lock = lock
    async with lock:
        existing = getattr(request.app.state, "extraction_service", None)
        if existing is not None:
            return cast(ExtractionService, existing)
        try:
            service = await build_extraction_service(os.getenv("EXTRACTION_CONFIG_PATH"))
        except Exception:  # noqa: BLE001 - configuration failures must not expose credentials
            raise HTTPException(
                status_code=503,
                detail={
                    "code": "extraction_unavailable",
                    "message": "Extraction service configuration is unavailable.",
                },
            ) from None
        request.app.state.extraction_service = service
        request.app.state.extraction_service_owned = True
        return service


def _parse_options(value: str) -> ExtractionOptions:
    if len(value.encode("utf-8")) > _MAX_OPTIONS_BYTES:
        raise _input_error("invalid_options")
    try:
        options = ExtractionOptions.model_validate(json.loads(value))
        if (
            options.max_pages > _SERVER_OPTIONS.max_pages
            or options.max_asset_bytes > _SERVER_OPTIONS.max_asset_bytes
            or options.timeout_seconds > _SERVER_OPTIONS.timeout_seconds
        ):
            raise _input_error("invalid_options")
        return options
    except (ValueError, ValidationError, RecursionError):
        raise _input_error("invalid_options") from None


def _parse_schema(value: str | None) -> ExternalSchema | None:
    if value is None:
        return None
    if len(value.encode("utf-8")) > _MAX_SCHEMA_BYTES:
        raise _input_error("invalid_schema")
    try:
        return _external_schema(json.loads(value))
    except (ValueError, ValidationError, RecursionError):
        raise _input_error("invalid_schema") from None


async def _read_upload(file: UploadFile, options: ExtractionOptions) -> PdfSource:
    filename = PurePosixPath((file.filename or "document.pdf").replace("\\", "/")).name
    if (
        not filename
        or not filename.lower().endswith(".pdf")
        or len(filename) > 255
        or any(ord(character) < 32 for character in filename)
    ):
        raise _input_error("invalid_pdf")
    limit = min(options.max_bytes, _MAX_UPLOAD_BYTES)
    payload = bytearray()
    while chunk := await file.read(min(_READ_CHUNK_BYTES, limit - len(payload) + 1)):
        payload.extend(chunk)
        if len(payload) > limit:
            raise HTTPException(
                status_code=413,
                detail={"code": "input_too_large", "message": "PDF exceeds the upload byte limit."},
            )
    if not payload.startswith(b"%PDF-"):
        raise _input_error("invalid_pdf")
    return PdfSource(data=bytes(payload), filename=filename)


def _service_error(error: ExtractionError) -> HTTPException:
    errors: dict[str, tuple[int, str]] = {
        "invalid_pdf": (422, "The PDF is invalid or unreadable."),
        "encrypted_pdf": (422, "Encrypted PDFs are not supported."),
        "invalid_page_range": (422, "The selected PDF page range is invalid."),
        "page_limit_exceeded": (422, "Selected pages exceed the configured limit."),
        "asset_limit_exceeded": (422, "PDF assets exceed the configured byte limit."),
        "input_too_large": (413, "PDF exceeds the input byte limit."),
        "invalid_schema": (422, "The external schema is invalid."),
        "schema_validation_failed": (422, "Extracted fields do not satisfy the external schema."),
        "conflicting_fields": (422, "Conflicting field candidates require review."),
        "no_source_text": (422, "Field extraction requires document text evidence."),
        "context_limit": (422, "Document input exceeds the selected model context."),
        "unknown_model_profile": (503, "The requested model profile is unavailable."),
        "unsupported_model_features": (503, "The model profile lacks a required feature."),
        "model_timeout": (504, "Model inference exceeded its deadline."),
        "workflow_timeout": (504, "Extraction exceeded its deadline."),
        "provider_error": (502, "The model provider could not complete extraction."),
        "model_response_invalid": (502, "The model provider returned an invalid response."),
        "model_oom": (503, "Model inference resources are unavailable."),
        "pdf_read_failed": (422, "The PDF could not be normalized safely."),
        "source_unavailable": (422, "The document source is unavailable."),
    }
    status, message = errors.get(error.code, (500, "Extraction could not be completed."))
    code = error.code if error.code in errors else "extraction_failed"
    return HTTPException(status_code=status, detail={"code": code, "message": message})


@router.post("/v1/extract", response_model=ExtractionResult)
async def extract_pdf(
    file: Annotated[UploadFile, File()],
    user: Annotated[UserContext, Depends(get_user_context)],
    service: Annotated[ExtractionService, Depends(get_extraction_service)],
    _limited: Annotated[None, Depends(_rate_limit)] = None,
    options_json: Annotated[str, Form()] = "{}",
    schema_definition: Annotated[str | None, Form(alias="schema_json")] = None,
) -> ExtractionResult:
    """Extract a PDF and optionally external-schema fields without persisting a job.

    Args:
        file: PDF upload; closed after the request completes or fails.
        options_json: Serialized extraction options, excluding provider credentials.
        schema_definition: Optional JSON Schema or versioned envelope from schema_json.
        user: Authenticated caller resolved by the host's existing auth dependency.
        service: Injected reusable extraction service.
        _limited: Inbound rate limit enforcement.

    Returns:
        Versioned document content and optional validated business data.
    """
    try:
        options = _parse_options(options_json)
        schema = _parse_schema(schema_definition)
        source = await _read_upload(file, options)
        return await service.extract(source, options=options, schema=schema)
    except ExtractionError as error:
        raise _service_error(error) from None
    except ValidationError:
        raise _input_error() from None
    except HTTPException:
        raise
    except Exception:  # noqa: BLE001 - never expose provider/document values through HTTP
        raise HTTPException(
            status_code=500,
            detail={"code": "extraction_failed", "message": "Extraction could not be completed."},
        ) from None
    finally:
        await file.close()


@router.post("/v1/extract/fields", response_model=FieldExtractionResult)
async def extract_fields(
    body: _FieldsRequest,
    user: Annotated[UserContext, Depends(get_user_context)],
    service: Annotated[ExtractionService, Depends(get_extraction_service)],
    _limited: Annotated[None, Depends(_rate_limit)] = None,
) -> FieldExtractionResult:
    """Apply an external schema to an existing document result without re-reading a PDF.

    Args:
        body: Validated document, external schema, logical profile, and timeout.
        user: Authenticated caller resolved by the host.
        service: Injected reusable extraction service.
        _limited: Inbound rate limit enforcement.

    Returns:
        Validated business data with separate source evidence and diagnostics.
    """
    try:
        return await service.extract_fields(
            body.document,
            body.external_schema,
            model_profile=body.model_profile,
            timeout_seconds=body.timeout_seconds,
        )
    except ExtractionError as error:
        raise _service_error(error) from None
    except ValidationError:
        raise _input_error() from None
    except Exception:  # noqa: BLE001 - never expose provider/document values through HTTP
        raise HTTPException(
            status_code=500,
            detail={"code": "extraction_failed", "message": "Field extraction failed."},
        ) from None
