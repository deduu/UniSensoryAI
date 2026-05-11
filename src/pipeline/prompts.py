"""Prompt registry — central store for VLM prompts.

Prompts are keyed by ``(document_subtype, region_type)`` and loaded from
``configs/prompts.yaml``. Resolution order:

    1. exact: ``{subtype}.{region_type}``
    2. fall back to ``generic.{region_type}``
    3. fall back to a built-in faithfulness prompt

The registry is a module-level singleton; call :func:`get_prompts` to access
it from anywhere. Tests can call :func:`reset_prompts` to clear cached state.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from src.utils.config import ConfigLoader

logger = logging.getLogger(__name__)

# Built-in fallback. Kept identical to the Phase 1 prompt so behaviour is
# unchanged when configs/prompts.yaml is absent.
_FAITHFUL_PAGE_PROMPT = (
    "Convert the visible document page into faithful Markdown. Transcribe every "
    "word, number, heading, table cell, label, checkbox, and footnote exactly as "
    "written. Preserve the original structure using Markdown headings, paragraphs, "
    "lists, and tables. Do not summarize, paraphrase, interpret, or omit content. "
    "Output only the Markdown extraction."
)

_BUILTIN_FALLBACK = {
    "page": _FAITHFUL_PAGE_PROMPT,
    "figure": (
        "Describe this figure faithfully. Transcribe every visible word, label, "
        "axis title, legend entry, and caption exactly as written. Output Markdown."
    ),
    "table": (
        "Extract this table as a GitHub-flavored Markdown table. Preserve column "
        "order and header row. Use the exact cell text as shown."
    ),
}


class PromptRegistry:
    """Resolve a prompt by ``(document_subtype, region_type)``.

    The registry lazy-loads ``configs/prompts.yaml`` on first lookup; if the
    file is missing or malformed it falls back to a small built-in map.
    """

    DEFAULT_PROMPT_ID = "generic.page"

    def __init__(self, config_path: Optional[Path] = None) -> None:
        self._config_path = config_path
        self._prompts: Optional[dict] = None

    def _load(self) -> dict:
        if self._prompts is not None:
            return self._prompts
        try:
            path = self._config_path or (
                ConfigLoader.DEFAULT_CONFIG_DIR / "prompts.yaml"
            )
            data = ConfigLoader.load_yaml(path) if path.exists() else {}
            self._prompts = data.get("prompts", {}) or {}
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "PromptRegistry: failed to load prompts.yaml (%s); "
                "using built-in fallback",
                exc,
            )
            self._prompts = {}
        return self._prompts

    def get(
        self,
        doc_subtype: Optional[str] = None,
        region_type: str = "page",
    ) -> str:
        """Return the prompt for ``(doc_subtype, region_type)``.

        Falls back to ``generic.{region_type}``, then to the built-in default.
        """
        prompts = self._load()
        region_type = region_type or "page"

        if doc_subtype:
            subtype_prompts = prompts.get(doc_subtype) or {}
            text = subtype_prompts.get(region_type)
            if isinstance(text, str) and text.strip():
                return text.strip()

        generic = prompts.get("generic") or {}
        text = generic.get(region_type)
        if isinstance(text, str) and text.strip():
            return text.strip()

        return _BUILTIN_FALLBACK.get(region_type, _FAITHFUL_PAGE_PROMPT)


_registry: Optional[PromptRegistry] = None


def get_prompts() -> PromptRegistry:
    """Return the module-level singleton."""
    global _registry
    if _registry is None:
        _registry = PromptRegistry()
    return _registry


def reset_prompts() -> None:
    """Reset the singleton — test-only seam."""
    global _registry
    _registry = None
