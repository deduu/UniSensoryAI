"""Version-checked package correction submitted by an external caller."""

from pydantic import PositiveInt

from src.paper.contracts._base import _Contract

from .package import InvoicePackage


class ReviseInvoiceCaseRequest(_Contract):
    """A replacement package and the latest revision the caller observed."""

    expected_version: PositiveInt
    package: InvoicePackage
