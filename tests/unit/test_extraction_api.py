"""Additive extraction routes use validated, authenticated service boundaries."""

import asyncio
import io
import json
from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI, HTTPException, UploadFile
from starlette.requests import Request

from src.api.auth import UserContext, get_user_context
from src.api.extraction_routes import extract_pdf, get_extraction_service, router
from src.extraction.contracts import (
    DocumentResult,
    ExternalSchema,
    ExtractionOptions,
    ExtractionResult,
    FieldExtractionResult,
    PageContent,
    PdfSource,
    TextBlock,
)
from src.extraction.errors import ExtractionError


def _document() -> DocumentResult:
    return DocumentResult(
        document_id="doc-123",
        source_name="invoice.pdf",
        content_mode="text",
        text="Invoice INV-123",
        pages=(
            PageContent(
                page_number=1,
                width=400,
                height=500,
                text_blocks=(
                    TextBlock(block_id="p1-text-1", page_number=1, text="Invoice INV-123"),
                ),
            ),
        ),
    )


def _schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {"invoice_number": {"type": "string"}},
        "required": ["invoice_number"],
    }


class _Service:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.error: Exception | None = None

    async def extract(
        self, source: PdfSource, *, options: ExtractionOptions, schema: ExternalSchema | None
    ) -> ExtractionResult:
        self.calls.append({"source": source, "options": options, "schema": schema})
        if self.error:
            raise self.error
        return ExtractionResult(document=_document())

    async def extract_fields(
        self,
        document: DocumentResult,
        schema: ExternalSchema,
        *,
        model_profile: str,
        timeout_seconds: float = 300,
    ) -> FieldExtractionResult:
        self.calls.append({"document": document, "schema": schema, "profile": model_profile})
        if self.error:
            raise self.error
        return FieldExtractionResult(
            schema_id=schema.schema_id,
            schema_version=schema.version,
            data={"invoice_number": "INV-123"},
        )


@pytest.fixture
def service() -> _Service:
    return _Service()


@pytest.fixture
def app(service: _Service) -> FastAPI:
    application = FastAPI()
    application.include_router(router)

    async def authenticated() -> UserContext:
        return UserContext(user_id="user", tenant_id="tenant")

    application.dependency_overrides[get_user_context] = authenticated
    application.dependency_overrides[get_extraction_service] = lambda: service
    return application


@pytest_asyncio.fixture
async def client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as api_client:
        yield api_client


@pytest.mark.asyncio
@pytest.mark.parametrize("option", ["max_pages", "max_asset_bytes", "timeout_seconds"])
async def test_caller_cannot_raise_server_resource_ceilings(
    client: httpx.AsyncClient, service: _Service, option: str
) -> None:
    response = await client.post(
        "/v1/extract",
        files={"file": ("document.pdf", b"%PDF-1.7", "application/pdf")},
        data={
            "options_json": json.dumps(
                {
                    option: {
                        "max_pages": 501,
                        "max_asset_bytes": 64 * 1024 * 1024 + 1,
                        "timeout_seconds": 301,
                    }[option]
                }
            )
        },
    )
    assert response.status_code == 422
    assert service.calls == []


@pytest.mark.asyncio
async def test_upload_validates_options_and_sanitizes_source_name(
    client: httpx.AsyncClient, service: _Service
) -> None:
    response = await client.post(
        "/v1/extract",
        files={"file": ("../../invoice.pdf", b"%PDF-1.7\nfake", "application/pdf")},
        data={"options_json": json.dumps({"content_mode": "multimodal"})},
    )
    assert response.status_code == 200
    assert response.json()["document"]["page_count"] == 1
    assert response.json()["schema_version"] == "1"
    assert service.calls[0]["source"].filename == "invoice.pdf"
    assert service.calls[0]["options"].content_mode == "multimodal"


@pytest.mark.asyncio
@pytest.mark.parametrize("envelope", [False, True])
async def test_upload_accepts_external_schema_definition_or_envelope(
    client: httpx.AsyncClient, service: _Service, envelope: bool
) -> None:
    schema = (
        {"schema_id": "invoice", "version": "2", "json_schema": _schema()}
        if envelope
        else _schema()
    )
    response = await client.post(
        "/v1/extract",
        files={"file": ("invoice.pdf", b"%PDF-1.7\nfake")},
        data={"schema_json": json.dumps(schema)},
    )
    assert response.status_code == 200
    assert service.calls[0]["schema"].json_schema == _schema()
    assert service.calls[0]["schema"].schema_id == ("invoice" if envelope else "external")


@pytest.mark.asyncio
async def test_fields_reuses_serialized_document_without_conversion(
    client: httpx.AsyncClient, service: _Service
) -> None:
    response = await client.post(
        "/v1/extract/fields",
        json={
            "document": _document().model_dump(mode="json"),
            "schema": {"schema_id": "invoice", "json_schema": _schema()},
            "model_profile": "invoice-fields",
        },
    )
    assert response.status_code == 200
    assert response.json()["data"]["invoice_number"] == "INV-123"
    assert service.calls[0]["document"].document_id == "doc-123"
    assert service.calls[0]["profile"] == "invoice-fields"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "form",
    [
        {"options_json": "{"},
        {"options_json": json.dumps({"content_mode": "secret-value"})},
        {"options_json": json.dumps({"api_key": "secret-value"})},
        {"schema_json": json.dumps({"type": "array", "description": "secret-value"})},
        {"schema_json": json.dumps({"type": "object", "$ref": "https://secret-value"})},
    ],
)
async def test_invalid_form_inputs_return_safe_validation_errors(
    client: httpx.AsyncClient, service: _Service, form: dict[str, str]
) -> None:
    response = await client.post(
        "/v1/extract", files={"file": ("invoice.pdf", b"%PDF-1.7\nfake")}, data=form
    )
    assert response.status_code == 422
    assert "secret-value" not in response.text
    assert service.calls == []


@pytest.mark.asyncio
async def test_fields_dto_validation_does_not_echo_document_values(
    client: httpx.AsyncClient, service: _Service
) -> None:
    response = await client.post(
        "/v1/extract/fields",
        json={"document": {"text": "secret-value"}, "schema": _schema()},
    )
    assert response.status_code == 422
    assert "secret-value" not in response.text
    assert service.calls == []


@pytest.mark.asyncio
async def test_server_upload_limit_cannot_be_increased_by_options(
    client: httpx.AsyncClient, service: _Service, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("src.api.extraction_routes._MAX_UPLOAD_BYTES", 20)
    response = await client.post(
        "/v1/extract",
        files={"file": ("invoice.pdf", b"%PDF-1.7\n" + b"x" * 30)},
        data={"options_json": json.dumps({"max_bytes": 100_000_000})},
    )
    assert response.status_code == 413
    assert service.calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("code", "status"),
    [
        ("invalid_pdf", 422),
        ("invalid_page_range", 422),
        ("schema_validation_failed", 422),
        ("unknown_model_profile", 503),
        ("unsupported_model_features", 503),
        ("model_timeout", 504),
        ("provider_error", 502),
    ],
)
async def test_service_failures_are_sanitized_and_mapped(
    client: httpx.AsyncClient, service: _Service, code: str, status: int
) -> None:
    service.error = ExtractionError(code, "secret-value provider document payload")
    response = await client.post("/v1/extract", files={"file": ("invoice.pdf", b"%PDF-1.7\nfake")})
    assert response.status_code == status
    assert response.json()["detail"]["code"] == code
    assert "secret-value" not in response.text


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["/v1/extract", "/v1/extract/fields"])
async def test_authentication_is_required_on_both_routes(
    app: FastAPI, client: httpx.AsyncClient, service: _Service, path: str
) -> None:
    async def unauthorized() -> UserContext:
        raise HTTPException(status_code=401, detail="Authentication required.")

    app.dependency_overrides[get_user_context] = unauthorized
    if path.endswith("fields"):
        response = await client.post(
            path, json={"document": _document().model_dump(mode="json"), "schema": _schema()}
        )
    else:
        response = await client.post(path, files={"file": ("invoice.pdf", b"%PDF-1.7\nfake")})
    assert response.status_code == 401
    assert service.calls == []


@pytest.mark.asyncio
async def test_upload_is_closed_when_options_are_invalid(service: _Service) -> None:
    upload = UploadFile(filename="invoice.pdf", file=io.BytesIO(b"%PDF-1.7\nfake"))
    with pytest.raises(HTTPException):
        await extract_pdf(
            file=upload,
            options_json="{",
            schema_definition=None,
            user=UserContext(user_id="user", tenant_id="tenant"),
            service=service,
        )
    assert upload.file.closed


@pytest.mark.asyncio
async def test_lazy_service_build_is_cached_and_marks_owned(
    monkeypatch: pytest.MonkeyPatch, service: _Service
) -> None:
    import src.api.extraction_routes as routes

    calls: list[str | None] = []

    async def build(config_path: str | None = None) -> _Service:
        calls.append(config_path)
        await asyncio.sleep(0)
        return service

    monkeypatch.setattr(routes, "build_extraction_service", build)
    monkeypatch.setenv("EXTRACTION_CONFIG_PATH", "config/extraction.yaml")
    app = FastAPI()
    asgi_request = Request({"type": "http", "app": app, "headers": []})
    first, second = await asyncio.gather(
        get_extraction_service(asgi_request), get_extraction_service(asgi_request)
    )
    assert first is second is service
    assert calls == ["config/extraction.yaml"]
    assert app.state.extraction_service_owned is True


@pytest.mark.asyncio
async def test_host_injected_service_is_reused_without_claiming_ownership(
    service: _Service,
) -> None:
    app = FastAPI()
    app.state.extraction_service = service
    request = Request({"type": "http", "app": app, "headers": []})
    assert await get_extraction_service(request) is service
    assert getattr(app.state, "extraction_service_owned", False) is False


@pytest.mark.asyncio
async def test_factory_failure_does_not_leak_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    import src.api.extraction_routes as routes

    async def failed(config_path: str | None = None) -> _Service:
        raise ValueError("secret-value API key in configuration")

    monkeypatch.setattr(routes, "build_extraction_service", failed)
    app = FastAPI()
    request = Request({"type": "http", "app": app, "headers": []})
    with pytest.raises(HTTPException) as caught:
        await get_extraction_service(request)
    assert caught.value.status_code == 503
    assert "secret-value" not in str(caught.value.detail)


def test_inbound_rate_limit_is_100_per_second_with_bounded_burst() -> None:
    import src.api.extraction_routes as routes

    assert routes._limiter.rate == 100
    assert routes._limiter.burst == 100
