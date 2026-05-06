"""Pipeline-specific exceptions."""


class PipelineError(Exception):
    """Base exception for pipeline errors."""

    pass


class PipelineValidationError(PipelineError):
    """Raised when a stage's input validation fails."""

    def __init__(self, stage_name: str, message: str) -> None:
        self.stage_name = stage_name
        super().__init__(f"Stage '{stage_name}' validation failed: {message}")


class PipelineStageError(PipelineError):
    """Raised when a stage encounters an unrecoverable error."""

    def __init__(self, stage_name: str, message: str) -> None:
        self.stage_name = stage_name
        super().__init__(f"Stage '{stage_name}' failed: {message}")


class PipelineTimeoutError(PipelineError):
    """Raised when a stage exceeds its timeout."""

    def __init__(self, stage_name: str, timeout_s: float) -> None:
        self.stage_name = stage_name
        self.timeout_s = timeout_s
        super().__init__(f"Stage '{stage_name}' timed out after {timeout_s}s")
