"""Party-role metadata stays source-derived, optional and independently reviewed."""

from copy import deepcopy
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from src.extraction.contracts import DocumentResult, FieldEvidence, PageContent, TextBlock
from src.extraction.schema_validation import SchemaValidationService
from src.paper.parties import (
    DeterministicPartyRoleValidator,
    PartyRoleSettings,
    get_party_roles_schema,
    load_party_role_settings,
    validate_party_roles,
)
from src.paper.schemas import RentAgreementSchema, get_paper_schema


def _terms(vendor_name: str | None = "Example Owner") -> RentAgreementSchema:
    return RentAgreementSchema(
        vendor_name=vendor_name,
        extensions={
            "host_attribute": "preserved",
            "party_roles": {
                "version": "1",
                "parties": [
                    {
                        "name": "Example Owner",
                        "role": "landlord",
                        "source_role": "YANG MENYEWAKAN",
                        "representatives": [],
                    },
                    {
                        "name": "Example Tenant Ltd.",
                        "role": "tenant",
                        "source_role": "PENYEWA",
                        "representatives": [
                            {
                                "name": "Example Director",
                                "represents": "Example Tenant Ltd.",
                                "capacity": "director",
                            }
                        ],
                    },
                ],
            },
        },
    )


def _document() -> DocumentResult:
    blocks = (
        TextBlock(block_id="p2", page_number=2, text="Example Owner"),
        TextBlock(block_id="p3", page_number=3, text="YANG MENYEWAKAN"),
        TextBlock(block_id="p4", page_number=4, text="Example Tenant Ltd. PENYEWA"),
        TextBlock(
            block_id="p5",
            page_number=5,
            text="Example Director acts for Example Tenant Ltd. as director.",
        ),
    )
    return DocumentResult(
        document_id="source",
        source_name="agreement.pdf",
        content_mode="text",
        text="\n".join(block.text for block in blocks),
        pages=tuple(
            PageContent(page_number=block.page_number, width=600, height=800, text_blocks=(block,))
            for block in blocks
        ),
    )


def _evidence() -> tuple[FieldEvidence, ...]:
    base = "/extensions/party_roles/parties"
    return (
        FieldEvidence(field_path="/vendor_name", source_ids=("p2",), quote="Example Owner"),
        FieldEvidence(field_path=f"{base}/0/name", source_ids=("p2",), quote="Example Owner"),
        FieldEvidence(
            field_path=f"{base}/0/source_role", source_ids=("p3",), quote="YANG MENYEWAKAN"
        ),
        FieldEvidence(field_path=f"{base}/1/name", source_ids=("p4",), quote="Example Tenant Ltd."),
        FieldEvidence(field_path=f"{base}/1/role", source_ids=("p4",), quote="PENYEWA"),
        FieldEvidence(
            field_path=f"{base}/1/representatives/0/name",
            source_ids=("p5",),
            quote="Example Director",
        ),
        FieldEvidence(
            field_path=f"{base}/1/representatives/0/represents",
            source_ids=("p5",),
            quote="Example Tenant Ltd.",
        ),
        FieldEvidence(
            field_path=f"{base}/1/representatives/0/capacity",
            source_ids=("p5",),
            quote="director",
        ),
    )


def _codes(
    terms: RentAgreementSchema, evidence: tuple[FieldEvidence, ...] | None = None
) -> set[str]:
    return {
        issue.code
        for issue in validate_party_roles(terms, evidence or _evidence(), document=_document())
    }


def test_optional_typed_metadata_preserves_absent_legacy_and_host_extensions() -> None:
    legacy = RentAgreementSchema(vendor_name="Example Owner")
    assert legacy.model_dump(mode="json")["extensions"] == {}
    assert _terms().extensions["host_attribute"] == "preserved"
    assert _terms().extensions["party_roles"]["parties"][0]["name"] == "Example Owner"


@pytest.mark.parametrize(
    "metadata",
    [
        {"version": "2", "parties": []},
        {"version": "1", "parties": [{"name": "A", "role": "supplier"}]},
        {"version": "1", "parties": [{"name": " ", "role": "unknown"}]},
        {"version": "1", "parties": [{"name": "A", "role": "landlord", "secret": "x"}]},
        {"version": "1", "parties": [{"representatives": [{"name": " "}]}]},
    ],
)
def test_invalid_party_metadata_is_rejected(metadata: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        RentAgreementSchema(extensions={"party_roles": metadata})


def test_unknown_party_values_stay_unknown_without_manufactured_names() -> None:
    terms = RentAgreementSchema(
        extensions={
            "party_roles": {
                "version": "1",
                "parties": [{"name": None, "role": "unknown", "source_role": None}],
            }
        }
    )
    party = terms.extensions["party_roles"]["parties"][0]
    assert party["name"] is None and party["source_role"] is None
    assert "party_roles_ambiguous" in _codes(terms)


@pytest.mark.parametrize("target", ["full", "targeted"])
def test_embedded_schema_references_resolve_and_validate_nested_representatives(
    target: str,
) -> None:
    schema = get_paper_schema("rent_agreement") if target == "full" else get_party_roles_schema()
    payload = {"vendor_name": _terms().vendor_name, "extensions": _terms().extensions}
    normalized = SchemaValidationService.validate(payload, schema)
    Draft202012Validator(schema.json_schema).validate(normalized)
    assert (
        normalized["extensions"]["party_roles"]["parties"][1]["representatives"][0]["name"]
        == "Example Director"
    )


def test_valid_multi_page_name_role_support_still_requires_human_review() -> None:
    terms = _terms()
    before = deepcopy(terms.model_dump(mode="json"))
    warnings = validate_party_roles(terms, _evidence(), document=_document())
    assert [item.code for item in warnings] == ["party_roles_review_required"]
    assert terms.model_dump(mode="json") == before
    assert warnings[0].field_path == "/extensions/party_roles"
    assert _codes(terms) == {"party_roles_review_required"}


def test_tenant_vendor_is_flagged_without_replacing_source_value() -> None:
    terms = _terms("Example Tenant Ltd.")
    warnings = validate_party_roles(terms, _evidence(), document=_document())
    assert "party_vendor_mismatch" in {item.code for item in warnings}
    assert terms.vendor_name == "Example Tenant Ltd."
    assert all("Example" not in item.message for item in warnings)


def test_representative_cannot_become_supplier_or_replace_principal() -> None:
    assert "party_vendor_mismatch" in _codes(_terms("Example Director"))


def test_duplicate_landlords_same_principal_and_missing_tenant_are_ambiguous() -> None:
    payload = _terms().model_dump(mode="json")
    parties = payload["extensions"]["party_roles"]["parties"]
    parties[1]["role"] = "landlord"
    assert "party_roles_ambiguous" in _codes(RentAgreementSchema.model_validate(payload))
    parties[1]["role"] = "tenant"
    parties[1]["name"] = "EXAMPLE OWNER"
    assert "party_principals_conflict" in _codes(RentAgreementSchema.model_validate(payload))


def test_role_labels_are_not_guessed_from_party_order_or_substrings() -> None:
    payload = _terms().model_dump(mode="json")
    parties = payload["extensions"]["party_roles"]["parties"]
    parties[0]["source_role"] = "PIHAK PERTAMA"
    parties[1]["source_role"] = "BUKAN PENYEWA"
    assert "party_role_unverified" in _codes(RentAgreementSchema.model_validate(payload))
    parties[0]["source_role"] = "PENYEWA"
    assert "party_role_conflict" in _codes(RentAgreementSchema.model_validate(payload))


def test_missing_or_unrelated_name_role_evidence_cannot_be_covered_by_vendor_quote() -> None:
    assert "party_evidence_missing" in _codes(_terms(), _evidence()[:1])
    refs = list(_evidence())
    refs[1] = refs[1].model_copy(update={"quote": "YANG MENYEWAKAN", "source_ids": ("p3",)})
    assert "party_name_unverified" in _codes(_terms(), tuple(refs))


@pytest.mark.parametrize("replacement", ["not-a-real-source", "p4"])
def test_unknown_ids_and_nonliteral_quotes_are_reported(replacement: str) -> None:
    refs = list(_evidence())
    refs[1] = refs[1].model_copy(update={"source_ids": (replacement,)})
    assert "party_evidence_invalid" in _codes(_terms(), tuple(refs))


def test_draft_only_validation_checks_retained_name_and_role_support() -> None:
    warnings = validate_party_roles(_terms(), _evidence())
    assert {item.code for item in warnings} == {"party_roles_review_required"}
    refs = tuple(item for item in _evidence() if not item.field_path.endswith("/source_role"))
    assert "party_evidence_missing" in {item.code for item in validate_party_roles(_terms(), refs)}


def test_normalized_name_equality_is_conservative_and_unicode_aware() -> None:
    assert "party_vendor_mismatch" not in _codes(_terms("  EXAMPLE OWNER  "))
    assert "party_vendor_mismatch" in _codes(_terms("Owner"))
    assert "party_vendor_missing" in _codes(_terms(None))


def test_legacy_missing_metadata_is_explicit_only_when_validator_is_invoked() -> None:
    warnings = validate_party_roles(RentAgreementSchema(), ())
    assert [item.code for item in warnings] == ["party_roles_missing"]


def test_host_role_lexicon_is_injected_and_cannot_overlap() -> None:
    settings = PartyRoleSettings(landlord_labels=("Owner",), tenant_labels=("Occupier",))
    payload = _terms().model_dump(mode="json")
    parties = payload["extensions"]["party_roles"]["parties"]
    parties[0]["source_role"] = "Owner"
    parties[1]["source_role"] = "Occupier"
    refs = tuple(
        (
            item.model_copy(update={"quote": "Owner"})
            if item.field_path.endswith("/0/source_role")
            else (
                item.model_copy(update={"quote": "Occupier"})
                if item.field_path.endswith("/1/role")
                else item
            )
        )
        for item in _evidence()
    )
    warnings = DeterministicPartyRoleValidator(settings).validate(
        RentAgreementSchema.model_validate(payload), refs
    )
    assert "party_role_unverified" not in {issue.code for issue in warnings}
    with pytest.raises(ValidationError):
        PartyRoleSettings(landlord_labels=("LESSOR",), tenant_labels=(" lessor ",))


@pytest.mark.asyncio
async def test_role_policy_loads_packaged_defaults_and_custom_yaml(tmp_path: Path) -> None:
    defaults = await load_party_role_settings()
    assert "YANG MENYEWAKAN" in defaults.landlord_labels
    config_path = tmp_path / "roles.yaml"
    config_path.write_text(
        "landlord_labels: [Owner]\ntenant_labels: [Occupier]\n", encoding="utf-8"
    )
    settings = await load_party_role_settings(config_path)
    assert settings.landlord_labels == ("Owner",)
    assert settings.tenant_labels == ("Occupier",)


@pytest.mark.asyncio
async def test_invalid_role_policy_has_safe_diagnostic(tmp_path: Path) -> None:
    config_path = tmp_path / "roles.yaml"
    config_path.write_text("landlord_labels: [PRIVATE_SAMPLE, PRIVATE_SAMPLE]", encoding="utf-8")
    with pytest.raises(ValueError, match="^Party role configuration is invalid.$"):
        await load_party_role_settings(config_path)


def test_declared_representative_attributes_require_field_specific_literal_support() -> None:
    refs = tuple(item for item in _evidence() if "/representatives/" not in item.field_path)
    warnings = validate_party_roles(_terms(), refs, document=_document())
    gaps = {item.field_path for item in warnings if item.code == "party_evidence_missing"}
    base = "/extensions/party_roles/parties/1/representatives/0"
    assert {f"{base}/{field}" for field in ("name", "represents", "capacity")} <= gaps


def test_representation_unknown_capacity_is_retained_but_unknown_principal_is_unresolved() -> None:
    payload = _terms().model_dump(mode="json")
    representative = payload["extensions"]["party_roles"]["parties"][1]["representatives"][0]
    representative["capacity"] = None
    warnings = validate_party_roles(RentAgreementSchema.model_validate(payload), _evidence())
    assert {item.code for item in warnings} == {"party_roles_review_required"}
    representative["represents"] = None
    warnings = validate_party_roles(RentAgreementSchema.model_validate(payload), _evidence())
    assert "party_representation_unverified" in {item.code for item in warnings}


def test_representation_chain_keeps_intermediaries_and_requires_known_terminal_principal() -> None:
    payload = _terms().model_dump(mode="json")
    representatives = payload["extensions"]["party_roles"]["parties"][1]["representatives"]
    representatives[0]["represents"] = "Example Attorney"
    representatives.append(
        {"name": "Example Attorney", "represents": "Example Tenant Ltd.", "capacity": None}
    )
    refs = tuple(item for item in _evidence() if "/representatives/" not in item.field_path)
    base = "/extensions/party_roles/parties/1/representatives"
    refs += tuple(
        FieldEvidence(
            field_path=f"{base}/{index}/{field}", source_ids=("retained-source",), quote=value
        )
        for index, representative in enumerate(representatives)
        for field, value in representative.items()
        if value is not None
    )
    warnings = validate_party_roles(RentAgreementSchema.model_validate(payload), refs)
    assert {item.code for item in warnings} == {"party_roles_review_required"}
    representatives.pop()
    warnings = validate_party_roles(RentAgreementSchema.model_validate(payload), refs)
    assert "party_representation_unverified" in {item.code for item in warnings}


def test_representation_cycles_cannot_establish_the_principal() -> None:
    payload = _terms().model_dump(mode="json")
    representatives = payload["extensions"]["party_roles"]["parties"][1]["representatives"]
    representatives[0]["represents"] = "Example Director"
    warnings = validate_party_roles(RentAgreementSchema.model_validate(payload), _evidence())
    assert "party_representation_unverified" in {item.code for item in warnings}
