"""Public reusable extraction facade; no HTTP, queue, or database dependencies."""

import asyncio
import copy

from src.extraction.capabilities import (
    DocumentExtractionCapability,
    DocumentExtractionInput,
    FieldExtractionCapability,
    FieldExtractionInput,
)
from src.extraction.capabilities.source_text import source_text_validation_warnings
from src.extraction.contracts import (
    DocumentResult,
    ExtractionOptions,
    ExtractionResult,
    FieldExtractionResult,
    PdfSource,
)
from src.extraction.errors import ExtractionError
from src.extraction.ports import (
    BaseCapability,
    BaseGenerationProvider,
    BaseModelGateway,
    BasePdfReader,
)
from src.extraction.schema_validation import SchemaInput, SchemaValidationService
from src.extraction.settings import ExtractionSettings


class ExtractionService:
    """Compose extraction operations while keeping business schemas external."""

    def __init__(
        self,
        *,
        reader: BasePdfReader,
        gateway: BaseModelGateway,
        settings: ExtractionSettings | None = None,
        document_capability: BaseCapability[DocumentExtractionInput, DocumentResult] | None = None,
        fields_capability: (
            BaseCapability[FieldExtractionInput, FieldExtractionResult] | None
        ) = None,
        owned_providers: tuple[BaseGenerationProvider, ...] = (),
    ) -> None:
        """Inject the reader, model gateway, and replaceable capabilities.

        Args:
            reader: Async PDF reader implementation.
            gateway: Model-neutral profile gateway.
            settings: Validated behavior overrides.
            document_capability: Optional host-supplied document operation.
            fields_capability: Optional host-supplied understanding operation.
            owned_providers: Composition-owned providers to release on close.
        """
        self._reader = reader
        self._settings = ExtractionSettings.model_validate(settings or ExtractionSettings())
        self._document = document_capability or DocumentExtractionCapability(
            gateway, self._settings
        )
        self._fields = fields_capability or FieldExtractionCapability(gateway, self._settings)
        self._owned_providers = tuple(
            {id(provider): provider for provider in owned_providers}.values()
        )
        self._closed = False

    async def aclose(self) -> None:
        """Close composition-owned providers; leave injected dependencies host-owned."""
        if not self._closed:
            self._closed = True
            results = await asyncio.gather(
                *(provider.aclose() for provider in self._owned_providers), return_exceptions=True
            )
            for result in results:
                if isinstance(result, asyncio.CancelledError):
                    raise result
                if isinstance(result, Exception):
                    raise ExtractionError(
                        "provider_error", "An extraction provider could not be closed."
                    ) from None

    def _ensure_open(self) -> None:
        if self._closed:
            raise ExtractionError("service_closed", "The extraction service is closed.")

    async def extract_document(
        self, source: PdfSource, options: ExtractionOptions | None = None
    ) -> DocumentResult:
        """Extract every selected PDF page in text or multimodal form.

        Args:
            source: Validated path or in-memory source.
            options: Representation, OCR selection, and budgets.

        Returns:
            Complete selected document representation with source evidence.
        """
        self._ensure_open()
        source = PdfSource.model_validate(source)
        selected = ExtractionOptions.model_validate(options or ExtractionOptions())
        try:
            return await asyncio.wait_for(
                self._read_and_extract(source, selected), selected.timeout_seconds
            )
        except asyncio.TimeoutError as exc:
            raise ExtractionError(
                "workflow_timeout", "Document extraction exceeded its deadline."
            ) from exc

    async def _read_and_extract(
        self, source: PdfSource, options: ExtractionOptions
    ) -> DocumentResult:
        normalized = await self._reader.read(source, options)
        result = await self._document.run(
            DocumentExtractionInput(document=normalized, options=options)
        )
        return DocumentResult.model_validate(result)

    async def extract_fields(
        self,
        document: DocumentResult,
        schema: SchemaInput,
        *,
        model_profile: str = "fields",
        timeout_seconds: float = 300,
    ) -> FieldExtractionResult:
        """Extract fields using an external JSON Schema or Pydantic business model.

        Args:
            document: Previously extracted document; no second PDF conversion.
            schema: External contract definition.
            model_profile: Logical provider profile for understanding.
            timeout_seconds: Total field extraction budget.

        Returns:
            Validated business payload and separately verified source evidence.
        """
        self._ensure_open()
        options = ExtractionOptions(fields_profile=model_profile, timeout_seconds=timeout_seconds)

        async def run() -> FieldExtractionResult:
            portable, business_model = await asyncio.to_thread(
                SchemaValidationService.resolve, schema
            )
            data = FieldExtractionInput(
                document=DocumentResult.model_validate(document),
                external_schema=portable,
                model_profile=options.fields_profile,
            )
            result = FieldExtractionResult.model_validate(await self._fields.run(data))
            validated = await asyncio.to_thread(
                SchemaValidationService.validate,
                copy.deepcopy(result.data),
                portable,
                business_model,
            )
            return FieldExtractionResult.model_validate(
                {
                    **result.model_dump(exclude={"status"}),
                    "data": validated,
                    "warnings": source_text_validation_warnings(result, validated),
                }
            )

        try:
            return await asyncio.wait_for(run(), options.timeout_seconds)
        except asyncio.TimeoutError as exc:
            raise ExtractionError(
                "workflow_timeout", "Field extraction exceeded its deadline."
            ) from exc

    async def extract(
        self,
        source: PdfSource,
        *,
        options: ExtractionOptions | None = None,
        schema: SchemaInput | None = None,
    ) -> ExtractionResult:
        """Compose document and optional business extraction under one deadline.

        Args:
            source: PDF source.
            options: Extraction behavior and model profile selection.
            schema: Optional external business schema.

        Returns:
            Combined versioned result, retaining source content.
        """
        self._ensure_open()
        selected = ExtractionOptions.model_validate(options or ExtractionOptions())

        async def run() -> ExtractionResult:
            document = await self.extract_document(source, selected)
            fields = (
                None
                if schema is None
                else await self.extract_fields(
                    document,
                    schema,
                    model_profile=selected.fields_profile,
                    timeout_seconds=selected.timeout_seconds,
                )
            )
            return ExtractionResult(document=document, fields=fields)

        try:
            return await asyncio.wait_for(run(), selected.timeout_seconds)
        except asyncio.TimeoutError as exc:
            raise ExtractionError("workflow_timeout", "Extraction exceeded its deadline.") from exc
