"""Safe business errors; source values never enter error messages."""


class AgreementMasterError(Exception):
    """A typed domain failure suitable for mapping at a transport boundary."""

    def __init__(self, code: str, message: str) -> None:
        """Initialize a safe failure.

        Args:
            code: Stable machine-readable failure category.
            message: Diagnostic without source document values.
        """
        super().__init__(message)
        self.code = code
