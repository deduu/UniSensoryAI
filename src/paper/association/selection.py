"""A reviewer's proposed contract selection, separate from source fields."""

from pydantic import PositiveInt

from src.paper.contracts._base import Identifier, Reason, _Contract


class AssociationSelection(_Contract):
    """Request explicit confirmation of one approved immutable agreement version."""

    agreement_id: Identifier
    version_number: PositiveInt
    reason: Reason
