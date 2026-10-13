"""Public extraction failures with stable codes and sanitized messages."""


class ExtractionError(RuntimeError):
    """An explicit failure, never an empty successful extraction."""

    def __init__(self, code: str, message: str) -> None:
        """Create a safe error.

        Args:
            code: Stable machine-readable category.
            message: Public message that excludes document values and credentials.
        """
        self.code = code
        super().__init__(message)
