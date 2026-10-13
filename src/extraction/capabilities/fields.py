"""Schema-driven extraction over every document block with explicit evidence."""

import asyncio
import copy
import json
import math
from collections.abc import Iterator
from dataclasses import dataclass
from typing import cast

import structlog
from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import ValidationError as JsonSchemaValidationError
from pydantic import JsonValue, ValidationError

from src.extraction.contracts import (
    ExtractionIssue,
    FieldEvidence,
    FieldExtractionResult,
    ImageAsset,
    ModelDescriptor,
    ModelRequest,
    TextBlock,
)
from src.extraction.errors import ExtractionError
from src.extraction.ports import BaseCapability, BaseModelGateway
from src.extraction.schema_utils import (
    make_generation_envelope_schema,
    relax_schema_requirements,
)
from src.extraction.schema_validation import SchemaValidationService
from src.extraction.settings import ExtractionSettings

from .field_input import FieldExtractionInput

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class _FieldChunk:
    blocks: list[dict[str, str]]
    images: tuple[ImageAsset, ...] = ()


def _reject_constant(value: str) -> float:
    raise ValueError("Nonfinite numbers are not valid extraction JSON.")


def _finite_float(value: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("Nonfinite numbers are not valid extraction JSON.")
    return number


def _merge(left: JsonValue, right: JsonValue) -> JsonValue:
    if left is None:
        return copy.deepcopy(right)
    if right is None:
        return left
    if isinstance(left, dict) and isinstance(right, dict):
        result = copy.deepcopy(left)
        for key, value in right.items():
            result[key] = _merge(result.get(key), value)
        return result
    if isinstance(left, list) and isinstance(right, list):
        return left + copy.deepcopy(right)
    if left != right:
        raise ExtractionError(
            "conflicting_fields",
            "Document chunks contain conflicting field candidates; review is required.",
        )
    return left


def _leaf_paths(value: JsonValue, prefix: str = "") -> Iterator[str]:
    if isinstance(value, dict):
        for key, item in value.items():
            escaped = key.replace("~", "~0").replace("/", "~1")
            yield from _leaf_paths(item, f"{prefix}/{escaped}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _leaf_paths(item, f"{prefix}/{index}")
    elif value is not None:
        yield prefix


def _rebase_evidence(evidence: FieldEvidence, old: dict[str, JsonValue]) -> FieldEvidence:
    parts = evidence.field_path.split("/")
    cursor: JsonValue = old
    for index, part in enumerate(parts[1:], 1):
        if isinstance(cursor, list) and part.isdigit():
            parts[index] = str(int(part) + len(cursor))
            break
        if isinstance(cursor, dict):
            cursor = cursor.get(part.replace("~1", "/").replace("~0", "~"))
        else:
            break
    return FieldEvidence(
        field_path="/".join(parts), source_ids=evidence.source_ids, quote=evidence.quote
    )


class FieldExtractionCapability(BaseCapability[FieldExtractionInput, FieldExtractionResult]):
    """Extract schema-shaped partial candidates, combine, and validate full data."""

    def __init__(self, gateway: BaseModelGateway, settings: ExtractionSettings) -> None:
        """Inject model routing and extraction behavior.

        Args:
            gateway: Host's model profile resolver and bounded generation service.
            settings: Prompt, retry, and output-token configuration.
        """
        self._gateway = gateway
        self._settings = settings

    def _prompt(self, definition: dict[str, JsonValue], blocks: list[dict[str, str]]) -> str:
        return (
            self._settings.fields_prompt
            + "\nImages provide layout context. Evidence quotes must appear literally in "
            "the supplied source blocks. Do not invent text evidence from an image."
            + "\nExternal schema:\n"
            + json.dumps(definition)
            + "\nSource blocks:\n"
            + json.dumps(blocks, ensure_ascii=False)
        )

    def _chunks(
        self, blocks: list[TextBlock], definition: dict[str, JsonValue], limit: int
    ) -> list[list[dict[str, str]]]:
        chunks: list[list[dict[str, str]]] = []
        current: list[dict[str, str]] = []
        if len(self._prompt(definition, [])) + 100 >= limit:
            raise ExtractionError(
                "context_limit", "Schema and prompt exceed the configured model context."
            )
        for block in blocks:
            remaining = block.text
            while remaining:
                entry = {"source_id": block.block_id, "text": remaining}
                if len(self._prompt(definition, current + [entry])) <= limit:
                    current.append(entry)
                    break
                if current:
                    chunks.append(current)
                    current = []
                    continue
                low, high = 1, len(remaining)
                while low < high:
                    midpoint = (low + high + 1) // 2
                    probe = [{"source_id": block.block_id, "text": remaining[:midpoint]}]
                    if len(self._prompt(definition, probe)) <= limit:
                        low = midpoint
                    else:
                        high = midpoint - 1
                piece = {"source_id": block.block_id, "text": remaining[:low]}
                if len(self._prompt(definition, [piece])) > limit:
                    raise ExtractionError(
                        "context_limit", "A source block cannot fit the model context."
                    )
                chunks.append([piece])
                remaining = remaining[low:]
        if current:
            chunks.append(current)
        return chunks

    def _document_chunks(
        self,
        data: FieldExtractionInput,
        descriptor: ModelDescriptor,
    ) -> tuple[list[_FieldChunk], list[TextBlock], list[ExtractionIssue]]:
        page_sources: list[tuple[list[TextBlock], tuple[ImageAsset, ...]]] = []
        warnings: list[ExtractionIssue] = []
        for page in data.document.pages:
            blocks = [block for block in page.text_blocks if block.text.strip()]
            known_texts = {block.text.strip() for block in blocks}
            for asset in page.images:
                description = (asset.description or "").strip()
                if description and description not in known_texts:
                    blocks.append(
                        TextBlock(
                            block_id=asset.asset_id,
                            page_number=page.page_number,
                            text=description,
                            bbox=asset.bbox,
                            origin="vision",
                        )
                    )
                    known_texts.add(description)
            if not blocks and page.images:
                warnings.append(
                    ExtractionIssue(
                        code="image_evidence_unavailable",
                        message="A page has no text evidence; enable OCR to verify its fields.",
                        page_number=page.page_number,
                    )
                )
            page_sources.append((blocks, page.images))
        sources = [block for blocks, _ in page_sources for block in blocks]
        if not sources:
            raise ExtractionError(
                "no_source_text",
                "Field extraction requires text evidence; enable OCR for scanned pages.",
            )
        use_images = (
            data.document.content_mode == "multimodal"
            and descriptor.supports_images
            and descriptor.max_images > 0
            and any(images for _, images in page_sources)
        )
        definition = data.external_schema.json_schema
        if not use_images:
            chunks = self._chunks(sources, definition, descriptor.max_input_chars)
            return [_FieldChunk(blocks=chunk) for chunk in chunks], sources, warnings
        output: list[_FieldChunk] = []
        for blocks, images in page_sources:
            previews = [image for image in images if image.kind == "page"]
            if previews:
                # A full-page raster already covers embedded images and vector layout.
                chunks = self._chunks(blocks, definition, descriptor.max_input_chars) or [[]]
                output.extend(_FieldChunk(chunk, (previews[0],)) for chunk in chunks)
                continue
            if not images:
                output.extend(
                    _FieldChunk(chunk)
                    for chunk in self._chunks(blocks, definition, descriptor.max_input_chars)
                )
                continue
            asset_block_ids = {
                identity
                for image in images
                for identity in (image.asset_id, f"{image.asset_id}-text")
            }
            native_blocks = [block for block in blocks if block.block_id not in asset_block_ids]
            for offset in range(0, len(images), descriptor.max_images):
                group = images[offset : offset + descriptor.max_images]
                group_ids = {
                    identity
                    for image in group
                    for identity in (image.asset_id, f"{image.asset_id}-text")
                }
                selected = [block for block in blocks if block.block_id in group_ids]
                if offset == 0:
                    selected = native_blocks + selected
                chunks = self._chunks(selected, definition, descriptor.max_input_chars) or [[]]
                output.extend(_FieldChunk(chunk, group) for chunk in chunks)
                if not selected and not any(
                    warning.page_number == group[0].page_number
                    and warning.code == "image_evidence_unavailable"
                    for warning in warnings
                ):
                    warnings.append(
                        ExtractionIssue(
                            code="image_evidence_unavailable",
                            message="An image has no text evidence; enable OCR to verify its fields.",
                            page_number=group[0].page_number,
                        )
                    )
        return output, sources, warnings

    async def run(self, data: FieldExtractionInput) -> FieldExtractionResult:
        """Read all selected source blocks; never truncate late pages.

        Args:
            data: Source content and caller-defined schema.

        Returns:
            Schema-valid fields and evidence, with explicit gaps or conflicts.
        """
        data = FieldExtractionInput.model_validate(data)
        descriptor = self._gateway.describe(data.model_profile)
        partial_schema = relax_schema_requirements(data.external_schema.json_schema)
        envelope_schema = make_generation_envelope_schema(partial_schema)
        chunks, blocks, warnings = self._document_chunks(data, descriptor)
        combined: dict[str, JsonValue] = {}
        evidence: list[FieldEvidence] = []
        for chunk in chunks:
            candidate, refs = await self._extract_chunk(
                data.model_profile,
                partial_schema,
                data.external_schema.json_schema,
                chunk.blocks,
                images=chunk.images,
                envelope_schema=envelope_schema if descriptor.supports_native_json else None,
            )
            evidence.extend(_rebase_evidence(item, combined) for item in refs)
            combined = cast(dict[str, JsonValue], _merge(combined, candidate))
        validated = await asyncio.to_thread(
            SchemaValidationService.validate, combined, data.external_schema
        )
        source_text = {block.block_id: block.text for block in blocks}
        paths = set(_leaf_paths(validated))
        verified: list[FieldEvidence] = []
        seen: set[str] = set()
        for item in evidence:
            quote = " ".join(item.quote.split())
            texts = [source_text.get(source_id) for source_id in item.source_ids]
            supported = (
                bool(quote)
                and all(text is not None for text in texts)
                and any(quote in " ".join(text.split()) for text in texts if text is not None)
            )
            if item.field_path not in paths or not supported:
                warnings.append(
                    ExtractionIssue(
                        code="invalid_evidence",
                        message="An evidence reference could not be verified.",
                        field_path=item.field_path,
                    )
                )
                continue
            verified.append(item)
            seen.add(item.field_path)
        for missing in sorted(paths - seen):
            warnings.append(
                ExtractionIssue(
                    code="missing_evidence",
                    message="An extracted field lacks verified source evidence.",
                    field_path=missing,
                )
            )
        logger.info("fields_extracted", chunk_count=len(chunks), warning_count=len(warnings))
        return FieldExtractionResult(
            schema_id=data.external_schema.schema_id,
            schema_version=data.external_schema.version,
            data=validated,
            evidence=tuple(verified),
            warnings=tuple(warnings),
        )

    async def _extract_chunk(
        self,
        profile: str,
        partial_schema: dict[str, JsonValue],
        full_schema: dict[str, JsonValue],
        blocks: list[dict[str, str]],
        *,
        images: tuple[ImageAsset, ...] = (),
        envelope_schema: dict[str, JsonValue] | None = None,
    ) -> tuple[dict[str, JsonValue], list[FieldEvidence]]:
        prompt = self._prompt(full_schema, blocks)
        for attempt in range(self._settings.field_attempts):
            response = await self._gateway.generate(
                profile,
                ModelRequest(
                    prompt=prompt,
                    purpose="fields",
                    max_output_tokens=self._settings.max_output_tokens,
                    images=images,
                    json_schema=envelope_schema,
                ),
            )
            try:
                content = response.content.strip()
                if content.startswith("```"):
                    _opening, separator, fenced = content.partition("\n")
                    if not separator or not fenced.rstrip().endswith("```"):
                        raise ValueError("Invalid JSON code fence")
                    content = fenced.rsplit("```", 1)[0]
                payload = json.loads(
                    content, parse_constant=_reject_constant, parse_float=_finite_float
                )
                if not isinstance(payload, dict) or set(payload) != {"data", "evidence"}:
                    raise ValueError("Invalid envelope")
                candidate = payload["data"]
                if not isinstance(candidate, dict) or not isinstance(payload["evidence"], list):
                    raise TypeError("Invalid envelope")
                await asyncio.to_thread(
                    Draft202012Validator(partial_schema, format_checker=FormatChecker()).validate,
                    candidate,
                )
                refs = [FieldEvidence.model_validate(item) for item in payload["evidence"]]
                return candidate, refs
            except (ValueError, TypeError, ValidationError, JsonSchemaValidationError):
                if attempt + 1 == self._settings.field_attempts:
                    raise ExtractionError(
                        "schema_validation_failed",
                        "Model output does not satisfy the external schema envelope.",
                    ) from None
        raise ExtractionError("schema_validation_failed", "No valid field extraction was produced.")
