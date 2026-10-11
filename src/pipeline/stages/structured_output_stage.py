"""Structured-output stage — extract typed JSON for known subtypes."""

from __future__ import annotations

import asyncio
import io
import json
import logging
import re
from typing import Any, Dict, List, Optional, Type

from PIL import Image
from pydantic import BaseModel, ValidationError

from src.core.base import BasePipelineStage
from src.inference.concurrency import get_registry
from src.structured.registry import SchemaRegistry, get_schema_registry

logger = logging.getLogger(__name__)

# Soft cap on prompt body to avoid blowing context windows on long docs.
_MAX_TEXT_CHARS = 20_000
_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)


def _blank_image_bytes() -> bytes:
    """Return PNG bytes for a 1×1 placeholder image.

    The current model API requires an image. For structured extraction we
    drive everything from the prompt and pass this throwaway image so the
    interface is honoured without affecting output.
    """
    buf = io.BytesIO()
    Image.new("RGB", (1, 1), color="white").save(buf, format="PNG")
    return buf.getvalue()


def _extract_json_payload(text: str) -> Optional[str]:
    """Try to isolate the first JSON object inside a free-form model reply."""
    if not text:
        return None

    fence = _JSON_FENCE_RE.search(text)
    if fence:
        candidate = fence.group(1).strip()
        if candidate.startswith("{"):
            return candidate

    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    in_string = False
    escape = False
    for idx in range(start, len(text)):
        ch = text[idx]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
        else:
            if ch == '"':
                in_string = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return text[start : idx + 1]
    return None


def _build_prompt(schema_cls: Type[BaseModel], doc_text: str, prior_error: Optional[str] = None) -> str:
    """Build the JSON-extraction prompt sent to the VLM."""
    schema_json = json.dumps(schema_cls.model_json_schema(), indent=2)
    parts = [
        f"You are extracting structured data into JSON that matches this schema:",
        "",
        schema_json,
        "",
        "Use ONLY the source text below. Do not invent values. Omit optional fields "
        "you cannot derive from the source. Output a single JSON object and nothing else.",
    ]
    if prior_error:
        parts += [
            "",
            "Your previous output failed validation with this error:",
            prior_error,
            "Fix the issue and output corrected JSON.",
        ]
    parts += [
        "",
        "Source text:",
        "---",
        doc_text,
        "---",
    ]
    return "\n".join(parts)


class StructuredOutputStage(BasePipelineStage):
    """Ask the VLM for schema-conformant JSON, validate, retry once on failure.

    Behaviour:

    - When ``document_subtype`` is ``None``, the stage is a no-op. This keeps
      cost down on documents that didn't get a specific subtype tag.
    - Otherwise it looks up a schema via :class:`SchemaRegistry`, asks the
      model for JSON, parses + validates with Pydantic, retries once with
      the validation error embedded in the prompt, and writes the result
      (or a non-fatal validation_error) to context.

    Reads:
        - ``raw_results`` (List[str]) — concatenated as source text.
        - ``model_instance`` — loaded VLM from InferenceStage.
        - ``model_id`` — for per-model semaphore.
        - ``document_subtype`` — drives schema selection.

    Writes:
        - ``structured_chunks`` (List[Dict[str, Any]])
        - ``validation_errors`` — appended only on failure.
    """

    def __init__(
        self,
        name: str = "structured_output",
        max_text_chars: int = _MAX_TEXT_CHARS,
        registry: Optional[SchemaRegistry] = None,
    ) -> None:
        super().__init__(name=name)
        self._max_text_chars = max_text_chars
        self._registry = registry

    def _get_registry(self) -> SchemaRegistry:
        return self._registry or get_schema_registry()

    def validate_input(self, context: Dict[str, Any]) -> bool:
        """Run only when raw_results and a model are present."""
        return (
            context.get("raw_results") is not None
            and len(context.get("raw_results", [])) > 0
            and context.get("model_id") is not None
            and context.get("model_instance") is not None
        )

    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        subtype: Optional[str] = context.get("document_subtype")
        if not subtype:
            logger.info(
                "structured_output: skipping — no document_subtype set"
            )
            return context

        schema_cls = self._get_registry().get(subtype)
        if schema_cls is None:
            logger.info(
                "structured_output: skipping — registry returned None for %s",
                subtype,
            )
            return context

        raw_results: List[str] = context["raw_results"]
        doc_text = "\n\n".join(r for r in raw_results if r).strip()
        if not doc_text:
            logger.info("structured_output: skipping — empty raw_results")
            return context
        if len(doc_text) > self._max_text_chars:
            doc_text = doc_text[: self._max_text_chars]

        model = context["model_instance"]
        model_id: str = context["model_id"]

        validated, err = await self._extract_once(
            model, model_id, schema_cls, doc_text, prior_error=None
        )
        if validated is None:
            # Retry once with the previous error embedded in the prompt.
            validated, err = await self._extract_once(
                model, model_id, schema_cls, doc_text, prior_error=err
            )

        if validated is None:
            errors: List[Dict[str, Any]] = context.setdefault("validation_errors", [])
            errors.append(
                {
                    "stage": "structured_output",
                    "schema_id": subtype,
                    "error": err or "validation failed",
                }
            )
            logger.warning(
                "structured_output: extraction failed for %s after retry: %s",
                subtype,
                err,
            )
            return context

        chunks: List[Dict[str, Any]] = context.get("structured_chunks") or []
        chunks.append(
            {
                "schema_id": subtype,
                "content": validated.model_dump(),
            }
        )
        context["structured_chunks"] = chunks
        logger.info(
            "structured_output: extracted %s with %d top-level keys",
            subtype,
            len(chunks[-1]["content"]),
        )
        return context

    async def _extract_once(
        self,
        model: Any,
        model_id: str,
        schema_cls: Type[BaseModel],
        doc_text: str,
        prior_error: Optional[str],
    ) -> tuple[Optional[BaseModel], Optional[str]]:
        """Single attempt: build prompt, call model, parse, validate.

        Returns ``(validated_model, None)`` on success or ``(None, error_str)``.
        """
        prompt = _build_prompt(schema_cls, doc_text, prior_error)
        semaphore = await get_registry().get(model_id)

        async with semaphore:
            loop = asyncio.get_event_loop()
            try:
                raw = await loop.run_in_executor(
                    None,
                    lambda b=_blank_image_bytes(), p=prompt: model.process(image=b, prompt=p),
                )
            except Exception as exc:  # noqa: BLE001
                return None, f"model call failed: {exc}"

        text = raw.get("content", "") if isinstance(raw, dict) else ""
        payload = _extract_json_payload(text)
        if payload is None:
            return None, "no JSON object found in model response"
        try:
            parsed = json.loads(payload)
        except json.JSONDecodeError as exc:
            return None, f"json decode error: {exc.msg}"

        if not isinstance(parsed, dict):
            return None, "top-level JSON must be an object"

        try:
            return schema_cls(**parsed), None
        except ValidationError as exc:
            return None, exc.json(indent=2)
