"""Agreement publication is distinct from extraction and always tenant scoped."""

from datetime import date, datetime, timezone
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from src.extraction.contracts import ExtractionIssue, FieldEvidence
from src.paper.contracts import (
    AgreementActor,
    AgreementDraft,
    AgreementEvidence,
    AgreementIdentity,
    AgreementLookup,
    AgreementVersion,
    ApprovalDecision,
    ApprovalRecord,
)
from src.paper.errors import AgreementMasterError
from src.paper.ports import BaseAgreementRepository
from src.paper.schemas import RentAgreementSchema
from src.paper.service import AgreementMasterService
from src.paper.settings import AgreementMasterSettings


def draft(**changes: object) -> AgreementDraft:
    values: dict[str, object] = {
        "terms": RentAgreementSchema(
            vendor_name="Landlord",
            vendor_id="vendor-1",
            store_id="store-1",
            contract_number="RA-1",
            lease_start_date="2026-01-01",
            lease_end_date="2026-12-31",
            payment_schedule="Monthly",
            rent_type="fixed",
            currency="IDR",
            fixed_rent="1000000.00",
        ),
        "effective_from": date(2026, 1, 1),
        "effective_to": date(2026, 12, 31),
        "source_document_ids": ("source-1",),
        "change_reason": "Initial terms",
    }
    values.update(changes)
    return AgreementDraft.model_validate(values)


def version(**changes: object) -> AgreementVersion:
    values: dict[str, object] = {
        "agreement_id": "agreement-1",
        "tenant_id": "tenant-1",
        "version_number": 1,
        "identity": AgreementIdentity(
            vendor_id="vendor-1", store_id="store-1", contract_number="RA-1"
        ),
        "draft": draft(),
        "created_by": "author",
        "created_at": datetime.now(timezone.utc),
    }
    values.update(changes)
    return AgreementVersion.model_validate(values)


def decision() -> ApprovalDecision:
    return ApprovalDecision(
        classification="psak73",
        rule_set_id="accounting-policy",
        rule_set_version="2026.1",
        reason="Reviewed against the approved accounting policy",
    )


@pytest.fixture
def repository() -> AsyncMock:
    repo = AsyncMock(spec=BaseAgreementRepository)
    repo.get_version.return_value = version()
    return repo


@pytest.fixture
def actor() -> AgreementActor:
    return AgreementActor(tenant_id="tenant-1", user_id="reviewer", can_approve=True)


@pytest.mark.asyncio
async def test_create_keeps_extraction_unapproved(
    repository: AsyncMock, actor: AgreementActor
) -> None:
    repository.create.return_value = version()
    service = AgreementMasterService(repository)
    result = await service.create_draft(actor=actor, identity=version().identity, draft=draft())
    assert result.status == "draft"
    assert result.approval is None
    repository.create.assert_awaited_once()


@pytest.mark.asyncio
async def test_mismatched_master_identity_cannot_be_saved(
    repository: AsyncMock, actor: AgreementActor
) -> None:
    terms = draft().terms.model_copy(update={"store_id": "another-store"})
    with pytest.raises(AgreementMasterError, match="identity"):
        await AgreementMasterService(repository).create_draft(
            actor=actor, identity=version().identity, draft=draft(terms=terms)
        )
    repository.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_missing_terms_can_be_draft_but_cannot_be_approved(
    repository: AsyncMock, actor: AgreementActor
) -> None:
    incomplete = version(draft=draft(terms=RentAgreementSchema()))
    repository.get_version.return_value = incomplete
    with pytest.raises(AgreementMasterError) as error:
        await AgreementMasterService(repository).approve(
            actor=actor, agreement_id="agreement-1", version_number=1, decision=decision()
        )
    assert error.value.code == "invalid_approval"
    repository.approve.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("require_all_identity_fields", [False, True])
async def test_publication_uses_assigned_identity_without_fabricating_source_identifiers(
    repository: AsyncMock, actor: AgreementActor, require_all_identity_fields: bool
) -> None:
    source_terms = draft().terms.model_copy(
        update={"vendor_id": None, "store_id": None, "contract_number": None}
    )
    source_draft = draft(terms=source_terms)
    snapshot = version(draft=source_draft)
    before = snapshot.model_dump(mode="json")
    repository.get_version.return_value = snapshot
    approval = ApprovalRecord(
        **decision().model_dump(), approved_by=actor.user_id, approved_at=datetime.now(timezone.utc)
    )
    repository.approve.return_value = version(draft=source_draft, approval=approval)
    settings = AgreementMasterSettings()
    if require_all_identity_fields:
        settings = AgreementMasterSettings(
            required_agreement_fields=(
                *settings.required_agreement_fields,
                "vendor_id",
                "contract_number",
            )
        )

    result = await AgreementMasterService(repository, settings=settings).approve(
        actor=actor, agreement_id="agreement-1", version_number=1, decision=decision()
    )

    assert result.status == "approved"
    assert result.identity == snapshot.identity
    assert result.draft == source_draft
    assert snapshot.model_dump(mode="json") == before
    for name in ("vendor_id", "store_id", "contract_number"):
        assert getattr(result.draft.terms, name) is None
    repository.approve.assert_awaited_once_with(
        agreement_id="agreement-1", version_number=1, decision=decision(), actor=actor
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("conflicting", ["vendor_id", "store_id", "contract_number"])
async def test_publication_rejects_source_identifiers_conflicting_with_assigned_identity(
    repository: AsyncMock, actor: AgreementActor, conflicting: str
) -> None:
    source_terms = draft().terms.model_copy(
        update={"vendor_id": None, "store_id": None, "contract_number": None, conflicting: "other"}
    )
    repository.get_version.return_value = version(draft=draft(terms=source_terms))
    with pytest.raises(AgreementMasterError, match="identity") as error:
        await AgreementMasterService(repository).approve(
            actor=actor, agreement_id="agreement-1", version_number=1, decision=decision()
        )
    assert error.value.code == "invalid_agreement"
    repository.approve.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("missing", ["vendor_name", "payment_schedule", "currency", "fixed_rent"])
async def test_assigned_identity_does_not_replace_missing_nonidentity_publication_terms(
    repository: AsyncMock, actor: AgreementActor, missing: str
) -> None:
    source_terms = draft().terms.model_copy(
        update={"vendor_id": None, "store_id": None, "contract_number": None, missing: None}
    )
    repository.get_version.return_value = version(draft=draft(terms=source_terms))
    with pytest.raises(AgreementMasterError, match="Required agreement terms") as error:
        await AgreementMasterService(repository).approve(
            actor=actor, agreement_id="agreement-1", version_number=1, decision=decision()
        )
    assert error.value.code == "invalid_approval"
    repository.approve.assert_not_awaited()


@pytest.mark.asyncio
async def test_assigned_identity_does_not_bypass_retained_warning_acknowledgement(
    repository: AsyncMock, actor: AgreementActor
) -> None:
    source_terms = draft().terms.model_copy(update={"store_id": None})
    repository.get_version.return_value = version(
        draft=draft(
            terms=source_terms,
            extraction_warnings=(ExtractionIssue(code="review", message="Review source."),),
        )
    )
    with pytest.raises(AgreementMasterError, match="warnings require explicit") as error:
        await AgreementMasterService(repository).approve(
            actor=actor, agreement_id="agreement-1", version_number=1, decision=decision()
        )
    assert error.value.code == "invalid_approval"
    repository.approve.assert_not_awaited()


@pytest.mark.asyncio
async def test_approval_requires_explicit_authority(repository: AsyncMock) -> None:
    member = AgreementActor(tenant_id="tenant-1", user_id="member")
    with pytest.raises(AgreementMasterError) as error:
        await AgreementMasterService(repository).approve(
            actor=member, agreement_id="agreement-1", version_number=1, decision=decision()
        )
    assert error.value.code == "forbidden"
    repository.approve.assert_not_awaited()


@pytest.mark.asyncio
async def test_publication_records_explicit_classification_and_rules(
    repository: AsyncMock, actor: AgreementActor
) -> None:
    approval = ApprovalRecord(
        **decision().model_dump(), approved_by="reviewer", approved_at=datetime.now(timezone.utc)
    )
    repository.approve.return_value = version(approval=approval)
    result = await AgreementMasterService(repository).approve(
        actor=actor, agreement_id="agreement-1", version_number=1, decision=decision()
    )
    assert result.status == "approved"
    assert result.approval.rule_set_version == "2026.1"
    assert repository.approve.await_args.kwargs["actor"].tenant_id == "tenant-1"


@pytest.mark.asyncio
async def test_independent_approval_is_a_host_policy(repository: AsyncMock) -> None:
    author = AgreementActor(tenant_id="tenant-1", user_id="author", can_approve=True)
    service = AgreementMasterService(
        repository, settings=AgreementMasterSettings(require_independent_approval=True)
    )
    with pytest.raises(AgreementMasterError) as error:
        await service.approve(
            actor=author, agreement_id="agreement-1", version_number=1, decision=decision()
        )
    assert error.value.code == "forbidden"


@pytest.mark.asyncio
async def test_revision_preserves_authoritative_identity(
    repository: AsyncMock, actor: AgreementActor
) -> None:
    repository.append.return_value = version(version_number=2)
    await AgreementMasterService(repository).revise(
        actor=actor,
        agreement_id="agreement-1",
        expected_version=1,
        draft=draft(change_reason="Corrected source"),
    )
    assert repository.append.await_args.kwargs["expected_version"] == 1
    assert repository.get_version.await_args.kwargs["tenant_id"] == "tenant-1"


@pytest.mark.asyncio
async def test_cross_tenant_missing_version_is_not_found(
    repository: AsyncMock, actor: AgreementActor
) -> None:
    repository.get_version.return_value = None
    with pytest.raises(AgreementMasterError) as error:
        await AgreementMasterService(repository).get_version(
            actor=actor, agreement_id="secret", version_number=1
        )
    assert error.value.code == "not_found"


@pytest.mark.asyncio
async def test_approved_lookup_passes_identity_date_and_tenant(
    repository: AsyncMock, actor: AgreementActor
) -> None:
    lookup = AgreementLookup(identity=version().identity, as_of=date(2026, 6, 1))
    repository.find_approved.return_value = None
    assert (
        await AgreementMasterService(repository).find_approved(actor=actor, lookup=lookup) is None
    )
    repository.find_approved.assert_awaited_once_with(tenant_id="tenant-1", lookup=lookup)


def test_source_evidence_must_belong_to_snapshot() -> None:
    evidence = AgreementEvidence(
        document_id="another-document",
        evidence=FieldEvidence(
            field_path="/vendor_name", source_ids=("p1-text-1",), quote="Landlord"
        ),
    )
    with pytest.raises(ValidationError):
        draft(evidence=(evidence,))


def test_effective_dates_and_source_ids_are_validated() -> None:
    with pytest.raises(ValidationError):
        draft(effective_to=date(2025, 12, 31))
    with pytest.raises(ValidationError):
        draft(source_document_ids=())
    with pytest.raises(ValidationError):
        draft(source_document_ids=("source-1", "source-1"))


def test_unknown_required_approval_field_is_configuration_error() -> None:
    with pytest.raises(ValidationError):
        AgreementMasterSettings(required_agreement_fields=("fabricated_field",))


@pytest.mark.asyncio
async def test_required_host_extensions_must_be_populated(
    repository: AsyncMock, actor: AgreementActor
) -> None:
    repository.get_version.return_value = version()
    service = AgreementMasterService(
        repository, settings=AgreementMasterSettings(required_agreement_fields=("extensions",))
    )
    with pytest.raises(AgreementMasterError) as error:
        await service.approve(
            actor=actor, agreement_id="agreement-1", version_number=1, decision=decision()
        )
    assert error.value.code == "invalid_approval"
    repository.approve.assert_not_awaited()


def test_approval_requires_classification_rule_and_reason() -> None:
    with pytest.raises(ValidationError):
        ApprovalDecision(
            classification="unknown", rule_set_id="rule", rule_set_version="1", reason="Review"
        )
    with pytest.raises(ValidationError):
        ApprovalDecision(
            classification="psak73", rule_set_id=" ", rule_set_version="1", reason="Review"
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("missing", ["currency", "fixed_rent"])
async def test_fixed_rent_cannot_be_published_with_missing_payment_terms(
    repository: AsyncMock, actor: AgreementActor, missing: str
) -> None:
    terms = draft().terms.model_copy(update={missing: None})
    repository.get_version.return_value = version(draft=draft(terms=terms))
    with pytest.raises(AgreementMasterError) as error:
        await AgreementMasterService(repository).approve(
            actor=actor, agreement_id="agreement-1", version_number=1, decision=decision()
        )
    assert error.value.code == "invalid_approval"
    repository.approve.assert_not_awaited()


def test_draft_retains_extraction_schema_identity() -> None:
    assert draft().schema_id == "paper.rent_agreement"
    assert draft().schema_version == "1"


@pytest.mark.asyncio
async def test_extraction_warnings_require_explicit_publication_acknowledgement(
    repository: AsyncMock, actor: AgreementActor
) -> None:
    warning = ExtractionIssue(code="missing_evidence", message="Source citation unavailable")
    warned = draft(extraction_warnings=(warning,))
    repository.get_version.return_value = version(draft=warned)
    service = AgreementMasterService(repository)
    with pytest.raises(AgreementMasterError) as error:
        await service.approve(
            actor=actor, agreement_id="agreement-1", version_number=1, decision=decision()
        )
    assert error.value.code == "invalid_approval"
    repository.approve.assert_not_awaited()
    acknowledged = ApprovalDecision.model_validate(
        {**decision().model_dump(), "acknowledge_extraction_warnings": True}
    )
    repository.approve.return_value = version(draft=warned)
    await service.approve(
        actor=actor, agreement_id="agreement-1", version_number=1, decision=acknowledged
    )
    assert repository.approve.await_args.kwargs["decision"].acknowledge_extraction_warnings is True


def _scheduled_draft(installment_id: str = "stage-1", amount: str = "100.00") -> AgreementDraft:
    body = draft().model_dump(mode="json")
    body["terms"]["installment_schedule"] = {
        "schedule_id": "lease-payments",
        "version": "1",
        "currency": "IDR",
        "total_gross": amount,
        "source_reference": "Article payment terms",
        "installments": [
            {
                "installment_id": installment_id,
                "gross_amount": amount,
                "coverage_start": "2026-01-01",
                "coverage_end": "2026-12-31",
                "conditions": [],
            }
        ],
    }
    return AgreementDraft.model_validate(body)


@pytest.mark.asyncio
@pytest.mark.parametrize("remove", [False, True])
async def test_saved_installment_ids_cannot_be_renamed_or_removed_in_revisions(
    repository: AsyncMock,
    actor: AgreementActor,
    remove: bool,
) -> None:
    previous = version(draft=_scheduled_draft())
    repository.get_version.return_value = previous
    replacement = draft() if remove else _scheduled_draft("new-id")
    with pytest.raises(AgreementMasterError, match="installment"):
        await AgreementMasterService(repository).revise(
            actor=actor, agreement_id="agreement-1", expected_version=1, draft=replacement
        )
    repository.append.assert_not_awaited()


@pytest.mark.asyncio
async def test_installment_amount_correction_retains_stable_obligation_id(
    repository: AsyncMock,
    actor: AgreementActor,
) -> None:
    repository.get_version.return_value = version(draft=_scheduled_draft())
    corrected = _scheduled_draft(amount="120.00")
    await AgreementMasterService(repository).revise(
        actor=actor, agreement_id="agreement-1", expected_version=1, draft=corrected
    )
    assert repository.append.await_args.kwargs["draft"] == corrected
