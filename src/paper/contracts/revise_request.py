"""Optimistic agreement revision input."""

from pydantic import PositiveInt

from ._base import _Contract
from .draft import AgreementDraft


class ReviseAgreementRequest(_Contract):
    """Append terms only when the caller still has the current version."""

    expected_version: PositiveInt
    draft: AgreementDraft
