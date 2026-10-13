"""OCR and visual extraction without model-specific code."""

import structlog

from src.extraction.contracts import (
    DocumentResult,
    ExtractionIssue,
    ImageAsset,
    ModelRequest,
    PageContent,
    TextBlock,
)
from src.extraction.ports import BaseCapability, BaseModelGateway
from src.extraction.settings import ExtractionSettings

from .document_input import DocumentExtractionInput

logger = structlog.get_logger(__name__)


class DocumentExtractionCapability(BaseCapability[DocumentExtractionInput, DocumentResult]):
    """Keep native content intact and infer only requested image units."""

    def __init__(self, gateway: BaseModelGateway, settings: ExtractionSettings) -> None:
        """Inject inference and behavior configuration.

        Args:
            gateway: Host-configured model routing boundary.
            settings: Validated prompt and output budgets.
        """
        self._gateway = gateway
        self._settings = settings

    async def run(self, data: DocumentExtractionInput) -> DocumentResult:
        """Extract every page without replacing native text.

        Args:
            data: Normalized input and independent representation/OCR choices.

        Returns:
            New document output with explicit warnings for skipped scanned content.
        """
        data = DocumentExtractionInput.model_validate(data)
        options = data.options
        pages: list[PageContent] = []
        warnings = list(data.document.warnings)
        for page in data.document.pages:
            blocks = [block for block in page.text_blocks if block.text.strip()]
            assets: list[ImageAsset] = []
            if page.is_scanned and options.text_strategy == "native_only":
                warnings.append(
                    ExtractionIssue(
                        code="ocr_skipped",
                        message="A page has no native text; OCR was not requested.",
                        page_number=page.page_number,
                    )
                )
            for asset in page.images:
                needs_inference = options.text_strategy == "native_then_ocr" and (
                    (page.is_scanned and asset.kind == "page")
                    or (not page.is_scanned and asset.kind == "image")
                )
                if needs_inference:
                    visual = options.content_mode == "multimodal" and not page.is_scanned
                    response = await self._gateway.generate(
                        options.vision_profile,
                        ModelRequest(
                            prompt=(
                                self._settings.vision_prompt
                                if visual
                                else self._settings.ocr_prompt
                            ),
                            images=(asset,),
                            purpose="vision" if visual else "ocr",
                            max_output_tokens=self._settings.max_output_tokens,
                        ),
                    )
                    content = response.content.strip()
                    blocks.append(
                        TextBlock(
                            block_id=f"{asset.asset_id}-text",
                            page_number=page.page_number,
                            text=content,
                            bbox=asset.bbox,
                            origin="vision" if visual else "ocr",
                        )
                    )
                    asset = ImageAsset.model_validate(
                        {**asset.model_dump(), "description": content}
                    )
                if options.content_mode == "multimodal":
                    assets.append(asset)
            pages.append(
                PageContent.model_validate(
                    {
                        **page.model_dump(),
                        "text_blocks": tuple(blocks),
                        "images": tuple(assets),
                        "tables": page.tables if options.content_mode == "multimodal" else (),
                    }
                )
            )
        text = self._settings.page_separator.join(
            "\n".join(block.text for block in page.text_blocks) for page in pages
        )
        logger.info("document_extracted", page_count=len(pages), warning_count=len(warnings))
        return DocumentResult(
            document_id=data.document.document_id,
            source_name=data.document.source_name,
            content_mode=options.content_mode,
            text=text,
            pages=tuple(pages),
            warnings=tuple(warnings),
        )
