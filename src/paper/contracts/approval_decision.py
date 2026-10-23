"""An explicit reviewer decision, independent of extraction output."""

from typing import Any, Literal, cast

from pydantic import SerializerFunctionWrapHandler, model_serializer

from ._base import Identifier, Reason, _Contract


class ApprovalDecision(_Contract):
    """Publish a classification with the accounting policy used and a reason."""

    classification: Literal["psak73", "non_psak73"]
    rule_set_id: Identifier
    rule_set_version: Identifier
    reason: Reason
    acknowledge_extraction_warnings: bool = False
    acknowledge_party_roles: bool = False

    @model_serializer(mode="wrap")
    def serialize_decision(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
        """Keep legacy payloads unchanged while retaining explicit party review.

        Args:
            handler: Pydantic serializer, including inherited approval audit fields.

        Returns:
            The complete decision, omitting the new flag when it was not accepted.
        """
        payload = cast(dict[str, Any], handler(self))
        if not self.acknowledge_party_roles:
            payload.pop("acknowledge_party_roles", None)
        return payload
