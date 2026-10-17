"""Explicit ownership for private artifacts not yet referenced by a committed document."""

from collections.abc import Awaitable, Callable
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class QueuedWorkflowResult(dict[str, Any]):
    """A normal document payload with cleanup confined to its creator-owned artifact."""

    def __init__(self, payload: dict[str, Any], *, discard: Callable[[], Awaitable[None]]) -> None:
        """Attach a private cleanup callback without adding it to serializable metadata."""
        super().__init__(payload)
        self._discard: Callable[[], Awaitable[None]] | None = discard

    def release_artifact(self) -> None:
        """Transfer ownership before a commit whose eventual outcome may be ambiguous."""
        self._discard = None

    async def discard_uncommitted_artifact(self) -> None:
        """Delete only output known not to have entered a completion commit."""
        discard, self._discard = self._discard, None
        if discard is not None:
            try:
                await discard()
            except OSError:
                logger.warning("uncommitted_workflow_artifact_cleanup_failed")
