"""Minimal authority reference attached to an assessed invoice package."""

from typing import Literal

from pydantic import PositiveInt

from src.paper.contracts._base import Identifier, _Contract


class AgreementReference(_Contract):
    """The approved agreement version and reviewer-owned classification used."""

    agreement_id: Identifier
    version_number: PositiveInt
    classification: Literal["psak73", "non_psak73"]
