"""Role-aware worker integration cannot downgrade fresh extraction to legacy review."""

import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from src.extraction.contracts import (
    DocumentResult,
    ExtractionOptions,
    FieldEvidence,
    FieldExtractionResult,
    PageContent,
    TextBlock,
)
from src.paper.extraction_contracts import PaperExtractionResult
from src.paper.parties import DeterministicPartyRoleValidator
from src.services.paper_extraction import PaperExtractionProcessor


def _source() -> DocumentResult:
    text = "Example Owner LANDLORD. Example Tenant TENANT."
    return DocumentResult(
        document_id="source-hash",
        source_name="contract.pdf",
        content_mode="text",
        text=text,
        pages=(
            PageContent(
                page_number=1,
                width=400,
                height=600,
                text_blocks=(TextBlock(block_id="p1", page_number=1, text=text),),
            ),
        ),
    )


def _base_fields(schema_name: str = "rent_agreement") -> FieldExtractionResult:
    return FieldExtractionResult(
        schema_id=f"paper.{schema_name}",
        schema_version="1",
        data={"vendor_name": "Example Tenant", "extensions": {"host_value": "keep"}},
        evidence=(
            FieldEvidence(field_path="/vendor_name", source_ids=("p1",), quote="Example Tenant"),
        ),
        model_ids=("base-provider-model",),
    )


def _party_fields() -> FieldExtractionResult:
    return FieldExtractionResult(
        schema_id="paper.agreement_party_roles",
        schema_version="1",
        data={
            "vendor_name": "Example Owner",
            "extensions": {
                "party_roles": {
                    "version": "1",
                    "parties": [
                        {"name": "Example Owner", "role": "landlord", "source_role": "LANDLORD"},
                        {"name": "Example Tenant", "role": "tenant", "source_role": "TENANT"},
                    ],
                },
            },
        },
        evidence=tuple(
            FieldEvidence(field_path=path, source_ids=("p1",), quote=quote)
            for path, quote in (
                ("/vendor_name", "Example Owner LANDLORD"),
                ("/extensions/party_roles/parties/0/name", "Example Owner"),
                ("/extensions/party_roles/parties/0/source_role", "LANDLORD"),
                ("/extensions/party_roles/parties/1/name", "Example Tenant"),
                ("/extensions/party_roles/parties/1/source_role", "TENANT"),
            )
        ),
        model_ids=("target-provider-model",),
    )


def _metadata(schema_name: str = "rent_agreement") -> dict[str, str | int]:
    return {
        "workflow": "paper_extraction",
        "schema_name": schema_name,
        "content_mode": "text",
        "original_filename": "contract.pdf",
        "file_size": 8,
    }


@pytest.mark.asyncio
async def test_agreement_processor_runs_targeted_pass_and_keeps_source_inputs_immutable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("UPLOADS_DIR", str(tmp_path))
    source_path = tmp_path / "source.pdf"
    source_path.write_bytes(b"%PDF-1.7")
    base = _base_fields()
    before = base.model_dump(mode="json")
    service = SimpleNamespace(
        extract_document=AsyncMock(return_value=_source()),
        extract_fields=AsyncMock(side_effect=[base, _party_fields()]),
    )
    processor = PaperExtractionProcessor(
        AsyncMock(return_value=service),
        options=ExtractionOptions(fields_profile="host-fields", timeout_seconds=1800),
        party_role_validator=DeterministicPartyRoleValidator(),
    )
    output = await processor.process(str(source_path), _metadata())
    artifact = tmp_path / output["chunks"][0]["artifact_name"]
    result = PaperExtractionResult.model_validate_json(artifact.read_text(encoding="utf-8"))
    assert result.fields is not None
    assert result.fields.data["vendor_name"] == "Example Owner"
    assert result.fields.data["extensions"]["host_value"] == "keep"
    assert base.model_dump(mode="json") == before
    assert service.extract_fields.await_count == 2
    assert service.extract_fields.await_args_list[1].args[0] == _source()
    assert (
        service.extract_fields.await_args_list[1].args[1].schema_id == "paper.agreement_party_roles"
    )
    assert service.extract_fields.await_args_list[1].kwargs == {
        "model_profile": "host-fields",
        "timeout_seconds": 1800,
    }
    assert output["job_metadata"]["model_ids"] == ["base-provider-model", "target-provider-model"]
    assert result.status == "partial"


@pytest.mark.asyncio
async def test_invoice_processor_preserves_existing_single_field_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("UPLOADS_DIR", str(tmp_path))
    source_path = tmp_path / "source.pdf"
    source_path.write_bytes(b"%PDF-1.7")
    service = SimpleNamespace(
        extract_document=AsyncMock(return_value=_source()),
        extract_fields=AsyncMock(return_value=_base_fields("rent_invoice")),
    )
    with patch("src.services.paper_extraction.load_party_role_settings") as policy:
        output = await PaperExtractionProcessor(AsyncMock(return_value=service)).process(
            str(source_path), _metadata("rent_invoice")
        )
    policy.assert_not_called()
    service.extract_fields.assert_awaited_once()
    artifact = tmp_path / output["chunks"][0]["artifact_name"]
    result = PaperExtractionResult.model_validate_json(artifact.read_text(encoding="utf-8"))
    assert result.fields is not None
    assert "party_roles" not in result.fields.data["extensions"]


@pytest.mark.asyncio
async def test_role_policy_failure_cannot_make_new_agreement_look_like_legacy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("UPLOADS_DIR", str(tmp_path))
    source_path = tmp_path / "source.pdf"
    source_path.write_bytes(b"%PDF-1.7")
    service = SimpleNamespace(
        extract_document=AsyncMock(return_value=_source()),
        extract_fields=AsyncMock(return_value=_base_fields()),
    )
    with patch(
        "src.services.paper_extraction.load_party_role_settings",
        AsyncMock(side_effect=ValueError("PRIVATE_CONFIG_DIAGNOSTIC")),
    ):
        output = await PaperExtractionProcessor(AsyncMock(return_value=service)).process(
            str(source_path), _metadata()
        )
    artifact = tmp_path / output["chunks"][0]["artifact_name"]
    result = PaperExtractionResult.model_validate_json(artifact.read_text(encoding="utf-8"))
    assert result.fields is not None
    assert result.fields.data["extensions"]["party_roles"]["parties"] == []
    assert any(issue.code.startswith("party_roles_") for issue in result.fields.warnings)
    assert "PRIVATE_CONFIG_DIAGNOSTIC" not in str(result.warnings + result.fields.warnings)
    assert result.fields.data["vendor_name"] == "Example Tenant"
    assert result.document == _source()


@pytest.mark.asyncio
async def test_cancellation_during_targeted_pass_propagates_without_artifact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("UPLOADS_DIR", str(tmp_path))
    source_path = tmp_path / "source.pdf"
    source_path.write_bytes(b"%PDF-1.7")
    service = SimpleNamespace(
        extract_document=AsyncMock(return_value=_source()),
        extract_fields=AsyncMock(side_effect=[_base_fields(), asyncio.CancelledError()]),
    )
    processor = PaperExtractionProcessor(
        AsyncMock(return_value=service), party_role_validator=DeterministicPartyRoleValidator()
    )
    with pytest.raises(asyncio.CancelledError):
        await processor.process(str(source_path), _metadata())
    assert list(tmp_path.glob("*.paper-extraction.json")) == []
