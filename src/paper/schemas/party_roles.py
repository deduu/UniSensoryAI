"""Optional typed party metadata embedded in external agreement extensions."""

from typing import Literal, cast

from pydantic import Field, JsonValue

from src.extraction.contracts.base import _Contract

from .agreement_party import AgreementParty


class PartyRoles(_Contract):
    """Source role candidates requiring explicit human review before publication."""

    version: Literal["1"] = "1"
    parties: tuple[AgreementParty, ...] = Field(
        max_length=32,
        description="All relevant legal principals, with independently evidenced landlord and tenant roles. Preserve ambiguity and unknown values; never invent external IDs. A role candidate is not verified solely because its name occurs in the document.",
    )


def party_roles_json_schema() -> dict[str, JsonValue]:
    """Return an inline schema safe to embed below arbitrary external-schema paths.

    Returns:
        Independent JSON Schema with local generated definitions expanded, so its
        references cannot accidentally resolve against a containing schema root.
    """
    definition = cast(dict[str, JsonValue], PartyRoles.model_json_schema())
    definitions = definition.get("$defs", {})

    def expand(value: JsonValue) -> JsonValue:
        if isinstance(value, list):
            return [expand(item) for item in value]
        if not isinstance(value, dict):
            return value
        reference = value.get("$ref")
        if isinstance(reference, str):
            if not reference.startswith("#/$defs/") or not isinstance(definitions, dict):
                raise ValueError("Party schema contains an unsupported local reference.")
            target = definitions.get(reference.removeprefix("#/$defs/"))
            if not isinstance(target, dict):
                raise TypeError("Party schema reference cannot be resolved.")
            return expand({**target, **{key: item for key, item in value.items() if key != "$ref"}})
        return {key: expand(item) for key, item in value.items() if key != "$defs"}

    return cast(dict[str, JsonValue], expand(definition))
