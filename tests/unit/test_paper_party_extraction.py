"""PAPER-specific role enrichment keeps generic extraction and history independent."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.extraction.contracts import (
    DocumentResult,
    ExtractionIssue,
    ExtractionOptions,
    FieldEvidence,
    FieldExtractionResult,
    PageContent,
    TextBlock,
)
from src.extraction.errors import ExtractionError
from src.services.paper_party_extraction import AgreementPartyExtractor


def source() -> DocumentResult:
    return DocumentResult(
        document_id="source",
        source_name="contract.pdf",
        content_mode="text",
        text="OWNER as LANDLORD; CLIENT as TENANT",
        pages=(
            PageContent(
                page_number=1,
                width=400,
                height=500,
                text_blocks=(
                    TextBlock(
                        block_id="p1", page_number=1, text="OWNER as LANDLORD; CLIENT as TENANT"
                    ),
                ),
            ),
        ),
    )


def result() -> FieldExtractionResult:
    return FieldExtractionResult(
        schema_id="paper.rent_agreement",
        schema_version="1",
        data={
            "vendor_name": "CLIENT",
            "payment_schedule": "Keep all conditions.",
            "extensions": {"fixed_rent_basis": "annual"},
        },
        evidence=(FieldEvidence(field_path="/vendor_name", source_ids=("p1",), quote="CLIENT"),),
        warnings=(ExtractionIssue(code="prior_warning", message="Retained warning."),),
        model_ids=("base-model",),
    )


@pytest.mark.asyncio
async def test_targeted_pass_merges_only_party_fields_without_mutating_previous_output() -> None:
    original = result()
    before = original.model_dump(mode="json")
    party = FieldExtractionResult(
        schema_id="paper.agreement_party_roles",
        schema_version="1",
        data={
            "vendor_name": "OWNER",
            "extensions": {
                "party_roles": {
                    "version": "1",
                    "parties": [
                        {
                            "name": "OWNER",
                            "role": "landlord",
                            "source_role": "LANDLORD",
                            "representatives": [],
                        },
                        {
                            "name": "CLIENT",
                            "role": "tenant",
                            "source_role": "TENANT",
                            "representatives": [],
                        },
                    ],
                }
            },
        },
        evidence=tuple(
            FieldEvidence(field_path=path, source_ids=("p1",), quote=quote)
            for path, quote in (
                ("/vendor_name", "OWNER as LANDLORD"),
                ("/extensions/party_roles/parties/0/name", "OWNER as LANDLORD"),
                ("/extensions/party_roles/parties/0/source_role", "OWNER as LANDLORD"),
                ("/extensions/party_roles/parties/1/name", "CLIENT as TENANT"),
                ("/extensions/party_roles/parties/1/source_role", "CLIENT as TENANT"),
            )
        ),
        model_ids=("role-model",),
    )
    service = SimpleNamespace(extract_fields=AsyncMock(return_value=party))
    enriched = await AgreementPartyExtractor(service).enrich(
        source(), original, ExtractionOptions()
    )
    assert original.model_dump(mode="json") == before
    assert enriched.data["vendor_name"] == "OWNER"
    assert enriched.data["payment_schedule"] == original.data["payment_schedule"]
    assert enriched.data["extensions"]["fixed_rent_basis"] == "annual"
    assert enriched.model_ids == ("base-model", "role-model")
    assert enriched.evidence == party.evidence
    assert {issue.code for issue in enriched.warnings} == {
        "prior_warning",
        "party_roles_review_required",
    }
    assert service.extract_fields.call_args.args[1].schema_id == "paper.agreement_party_roles"


@pytest.mark.asyncio
async def test_failed_role_pass_retains_fields_but_cannot_look_role_verified() -> None:
    service = SimpleNamespace(
        extract_fields=AsyncMock(side_effect=ExtractionError("timeout", "private"))
    )
    enriched = await AgreementPartyExtractor(service).enrich(
        source(), result(), ExtractionOptions()
    )
    assert enriched.data["vendor_name"] == "CLIENT"
    assert enriched.data["extensions"]["party_roles"]["parties"] == []
    assert "private" not in str(enriched.warnings)
    assert "party_roles_extraction_failed" in {issue.code for issue in enriched.warnings}


@pytest.mark.asyncio
async def test_invalid_role_payload_cannot_replace_other_terms_or_erase_evidence() -> None:
    service = SimpleNamespace(
        extract_fields=AsyncMock(
            return_value=FieldExtractionResult(
                schema_id="paper.agreement_party_roles",
                schema_version="1",
                data={"vendor_name": "OWNER", "extensions": {"party_roles": "bad"}},
            )
        )
    )
    original = result()
    enriched = await AgreementPartyExtractor(service).enrich(
        source(), original, ExtractionOptions()
    )
    assert enriched.data["payment_schedule"] == original.data["payment_schedule"]
    assert enriched.evidence == original.evidence
    assert "party_roles_extraction_failed" in {issue.code for issue in enriched.warnings}
