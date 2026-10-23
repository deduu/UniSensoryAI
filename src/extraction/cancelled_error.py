"""Typed graceful cancellation carrying safe usage to the worker handoff."""

import asyncio

from .contracts.usage import ExtractionUsage


class ExtractionCancelledError(asyncio.CancelledError):
    """Preserve measured and unknown attempted calls without suppressing cancellation."""

    def __init__(self, usage_summary: ExtractionUsage) -> None:
        """Attach immutable diagnostics; include no document/provider payload."""
        self.usage_summary = ExtractionUsage.model_validate(usage_summary)
        super().__init__("Extraction was interrupted.")
