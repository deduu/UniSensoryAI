"""Public extraction failures with stable codes and sanitized messages."""

from collections.abc import Mapping

from src.extraction.contracts.usage import ExtractionUsage


class ExtractionError(RuntimeError):
    """An explicit failure, never an empty successful extraction."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        usage: Mapping[str, int] | None = None,
        usage_summary: ExtractionUsage | None = None,
        response_model_id: str | None = None,
    ) -> None:
        """Create a safe error.

        Args:
            code: Stable machine-readable category.
            message: Public message that excludes document values and credentials.
            usage: Safe provider counters retained even when output is rejected.
            usage_summary: Optional typed workflow ledger for durable failure accounting.
            response_model_id: Provider-reported model identity for price binding.
        """
        self.code = code
        self.usage = {
            key: value
            for key, value in (usage or {}).items()
            if isinstance(key, str)
            and isinstance(value, int)
            and not isinstance(value, bool)
            and value >= 0
        }
        self.usage_summary = (
            ExtractionUsage.model_validate(usage_summary) if usage_summary is not None else None
        )
        self.response_model_id = response_model_id
        super().__init__(message)
