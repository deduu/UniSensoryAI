"""Expected-version append request; prior review is never carried forward."""

from pydantic import Field

from .create_request import CreateDocumentDraftRequest


class ReviseDocumentDraftRequest(CreateDocumentDraftRequest):
    """Append corrected fields with an explicit latest-version guard."""

    expected_version: int = Field(ge=1, strict=True)
