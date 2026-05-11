"""Prompt registry — central store for VLM prompts.

Phase 1 introduces the registry with a single entry (the existing
faithfulness prompt previously inlined in ``inference_stage.py``). Phase 2
expands it into a per-(doc_subtype, region_type) lookup backed by
``configs/prompts.yaml``.
"""

from typing import Optional

_FAITHFUL_PAGE_PROMPT = (
    "Convert the visible document page into faithful Markdown. Transcribe every "
    "word, number, heading, table cell, label, checkbox, and footnote exactly as "
    "written. Preserve the original structure using Markdown headings, paragraphs, "
    "lists, and tables. Do not summarize, paraphrase, interpret, or omit content. "
    "Output only the Markdown extraction."
)


class PromptRegistry:
    """Resolve a prompt by ``(document_subtype, region_type)``.

    Phase 1 returns the faithfulness prompt for every key; the signature
    exists now so Phase 2 can specialise without touching callers.
    """

    DEFAULT_PROMPT_ID = "generic.page"

    def get(
        self,
        doc_subtype: Optional[str] = None,
        region_type: str = "page",
    ) -> str:
        """Return the prompt for the requested key.

        Phase 1 ignores both arguments. Phase 2 will key off
        ``(doc_subtype, region_type)`` and load prompts from
        ``configs/prompts.yaml``.
        """
        return _FAITHFUL_PAGE_PROMPT


_registry: Optional[PromptRegistry] = None


def get_prompts() -> PromptRegistry:
    """Return the module-level singleton."""
    global _registry
    if _registry is None:
        _registry = PromptRegistry()
    return _registry
