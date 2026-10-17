"""Cancellation retains the source ownership transferred to a committed job."""

import asyncio


class QueueSubmissionCancelledError(asyncio.CancelledError):
    """Preserve cancellation while identifying an already committed upload."""

    def __init__(self, job_id: str) -> None:
        """Retain the committed job identifier without exposing backend details.

        Args:
            job_id: Identifier whose database transaction already committed.
        """
        super().__init__("Queue submission was cancelled after the job was persisted.")
        self.persisted_job_id = job_id
