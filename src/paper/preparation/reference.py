"""Exact immutable draft version chosen by a reviewer."""

from pydantic import PositiveInt

from src.paper.contracts._base import Identifier, _Contract


class DocumentVersionReference(_Contract):
    """Identify a saved document without accepting client-provided source fields."""

    draft_id: Identifier
    version_number: PositiveInt
