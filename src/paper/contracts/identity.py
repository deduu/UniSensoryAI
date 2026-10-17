"""Stable business identity of an agreement."""

from ._base import Identifier, _Contract


class AgreementIdentity(_Contract):
    """Canonical master identifiers; do not resolve names through an LLM."""

    vendor_id: Identifier
    store_id: Identifier
    contract_number: Identifier
