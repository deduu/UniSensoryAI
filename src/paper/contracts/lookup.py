"""Approved master lookup criteria."""

from datetime import date

from ._base import _Contract
from .identity import AgreementIdentity


class AgreementLookup(_Contract):
    """Find an approved version for an exact identity and business date."""

    identity: AgreementIdentity
    as_of: date
