"""Draft authors submit source values and explicit review intent only."""

from pydantic import StrictBool

from src.paper.contracts._base import Reason

from .content import DocumentDraftContent


class CreateDocumentDraftRequest(DocumentDraftContent):
    """Save source review independently of case matching and accounting approval."""

    reviewed: StrictBool = False
    reason: Reason
