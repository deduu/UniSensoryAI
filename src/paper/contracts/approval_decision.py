"""An explicit reviewer decision, independent of extraction output."""

from typing import Literal

from ._base import Identifier, Reason, _Contract


class ApprovalDecision(_Contract):
    """Publish a classification with the accounting policy used and a reason."""

    classification: Literal["psak73", "non_psak73"]
    rule_set_id: Identifier
    rule_set_version: Identifier
    reason: Reason
    acknowledge_extraction_warnings: bool = False
