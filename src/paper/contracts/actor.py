"""Trusted identity supplied by the embedding host."""

from ._base import Identifier, _Contract


class AgreementActor(_Contract):
    """Tenant scope and approval authority established outside request payloads."""

    tenant_id: Identifier
    user_id: Identifier
    can_approve: bool = False
