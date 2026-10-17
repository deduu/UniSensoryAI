"""Create agreement API and embedding input."""

from ._base import _Contract
from .draft import AgreementDraft
from .identity import AgreementIdentity


class CreateAgreementRequest(_Contract):
    """Initial terms and canonical identity, without caller-selected tenant or actor."""

    identity: AgreementIdentity
    draft: AgreementDraft
