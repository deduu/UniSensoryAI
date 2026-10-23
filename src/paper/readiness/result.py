"""Version-bound, read-only readiness response for an exact selected package."""

from typing import Annotated

from pydantic import Field, StringConstraints

from src.paper.contracts._base import Identifier, _Contract

from .check import ReadinessCheck


class ReadinessResult(_Contract):
    """Permit comparison only after all missing prerequisites have been resolved."""

    ready: bool
    policy_id: Identifier
    policy_version: Identifier
    policy_fingerprint: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
    package_fingerprint: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
    checks: tuple[ReadinessCheck, ...] = Field(default=(), max_length=10000)
