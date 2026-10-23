"""Portable targeted party extraction using complete representation clauses."""

from pydantic import JsonValue

from src.extraction.contracts import ExternalSchema
from src.paper.schemas.party_roles import party_roles_json_schema


def get_party_roles_schema() -> ExternalSchema:
    """Build a provider-neutral schema for a separate complete party-role pass.

    Returns:
        Targeted source-derived landlord name and optional typed extension metadata,
        preserving representatives, operative role labels and multipage citations.
    """
    definition: dict[str, JsonValue] = {
        "type": "object",
        "description": "Read every party-definition clause and continuation across the complete document. Follow each 'acting for and on behalf of', 'dalam hal ini bertindak', 'untuk dan atas nama' representation chain to its legal principal. Preserve ALL intermediaries: when attorney A acts for director B acting for company C, record separate A->B and B->C representatives; never collapse A->C or omit B. Cite each known representative name, represents step and capacity using original source language; keep unknown capacity null. Extract landlord and tenant independently; do not select the most frequent name, first signatory, cover name, invoice payee or notary. A source name occurrence or connected candidate chain is not role verification or proof of completeness. Retain unknown roles and explicit null values; require human review.",
        "properties": {
            "vendor_name": {
                "type": ["string", "null"],
                "minLength": 1,
                "maxLength": 256,
                "description": "Re-extract the legal landlord/rent supplier established by operative role clauses and representation chains. Exclude tenant/customer and people merely signing for an entity. Must equal the unique source-supported landlord principal; null if ambiguous. Cite both the principal name and role, including separate pages where needed.",
            },
            "extensions": {
                "type": "object",
                "properties": {"party_roles": party_roles_json_schema()},
                "required": ["party_roles"],
                "additionalProperties": True,
            },
        },
        "required": ["vendor_name", "extensions"],
        "additionalProperties": False,
    }
    return ExternalSchema(
        schema_id="paper.agreement_party_roles", version="1", json_schema=definition
    )
