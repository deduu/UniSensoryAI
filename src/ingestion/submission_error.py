"""Safe queue outcome for a source already owned by a committed job."""


class QueueSubmissionError(RuntimeError):
    """Report publication failure without losing the committed source owner."""

    def __init__(self, job_id: str) -> None:
        """Retain the durable job identifier without exposing backend details.

        Args:
            job_id: Identifier whose database transaction already committed.
        """
        super().__init__("The persisted job could not be published to the queue.")
        self.persisted_job_id = job_id
