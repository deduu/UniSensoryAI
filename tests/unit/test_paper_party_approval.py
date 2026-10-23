"""Party-role publication requires a separate review and retains legacy history."""

from collections.abc import Sequence
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock

import pytest

from src.extraction.contracts import DocumentResult, ExtractionIssue, FieldEvidence
from src.paper.contracts import (
    AgreementActor,
    AgreementDraft,
    AgreementEvidence,
    AgreementIdentity,
    AgreementVersion,
    ApprovalDecision,
    ApprovalRecord,
)
from src.paper.errors import AgreementMasterError
from src.paper.parties.validator import BasePartyRoleValidator
from src.paper.ports import BaseAgreementRepository
from src.paper.schemas import RentAgreementSchema
from src.paper.service import AgreementMasterService


class _RoleValidator(BasePartyRoleValidator):
    def __init__(self, *codes: str) -> None:
        self.issues = tuple(
            ExtractionIssue(code=code, message="Review required.") for code in codes
        )
        self.calls: list[tuple[RentAgreementSchema, tuple[FieldEvidence, ...]]] = []

    def validate(
        self,
        terms: RentAgreementSchema,
        evidence: Sequence[FieldEvidence],
        *,
        document: DocumentResult | None = None,
    ) -> tuple[ExtractionIssue, ...]:
        self.calls.append((terms, tuple(evidence)))
        return self.issues


def _draft(*, roles: bool = True, warnings: bool = False) -> AgreementDraft:
    return AgreementDraft(
        terms=RentAgreementSchema(
            vendor_name="Example Owner",
            vendor_id="vendor-1",
            store_id="store-1",
            contract_number="RA-1",
            lease_start_date="2026-01-01",
            lease_end_date="2026-12-31",
            payment_schedule="Monthly",
            rent_type="fixed",
            currency="IDR",
            fixed_rent="1000000.00",
            extensions=(
                {
                    "party_roles": {
                        "version": "1",
                        "parties": [
                            {"name": "Example Owner", "role": "landlord", "source_role": "LESSOR"},
                            {"name": "Example Tenant", "role": "tenant", "source_role": "LESSEE"},
                        ],
                    }
                }
                if roles
                else {}
            ),
        ),
        effective_from=date(2026, 1, 1),
        effective_to=date(2026, 12, 31),
        source_document_ids=("source-1",),
        evidence=(
            (
                AgreementEvidence(
                    document_id="source-1",
                    evidence=FieldEvidence(
                        field_path="/extensions/party_roles/parties/0/name",
                        source_ids=("p2",),
                        quote="Example Owner",
                    ),
                ),
            )
            if roles
            else ()
        ),
        extraction_warnings=(
            (ExtractionIssue(code="missing_evidence", message="Review warning."),)
            if warnings
            else ()
        ),
        change_reason="Reviewed source correction",
    )


def _version(draft: AgreementDraft | None = None) -> AgreementVersion:
    return AgreementVersion(
        agreement_id="agreement-1",
        tenant_id="tenant-1",
        version_number=4,
        identity=AgreementIdentity(
            vendor_id="vendor-1", store_id="store-1", contract_number="RA-1"
        ),
        draft=draft or _draft(),
        created_by="author",
        created_at=datetime(2026, 10, 17, tzinfo=timezone.utc),
    )


def _decision(*, roles: bool = False, warnings: bool = False) -> ApprovalDecision:
    values: dict[str, object] = {
        "classification": "psak73",
        "rule_set_id": "rent",
        "rule_set_version": "2026.1",
        "reason": "Verified principals and accounting classification against source",
        "acknowledge_extraction_warnings": warnings,
    }
    if roles:
        values["acknowledge_party_roles"] = True
    return ApprovalDecision.model_validate(values)


@pytest.fixture
def actor() -> AgreementActor:
    return AgreementActor(tenant_id="tenant-1", user_id="reviewer", can_approve=True)


@pytest.fixture
def repository() -> AsyncMock:
    result = AsyncMock(spec=BaseAgreementRepository)
    result.get_version.return_value = _version()
    result.approve.return_value = _version()
    result.append.return_value = _version()
    return result


def test_legacy_decision_and_approval_serialization_keep_their_original_shape() -> None:
    decision = _decision()
    payload = decision.model_dump(mode="json")
    assert "acknowledge_party_roles" not in payload
    assert decision.acknowledge_party_roles is False
    approval = ApprovalRecord(
        **payload,
        approved_by="reviewer",
        approved_at=datetime(2026, 10, 17, tzinfo=timezone.utc),
    )
    assert approval.model_dump(mode="json") == {
        **payload,
        "approved_by": "reviewer",
        "approved_at": "2026-10-17T00:00:00Z",
    }


def test_new_acknowledgement_roundtrips_with_inherited_approval_audit() -> None:
    decision = _decision(roles=True)
    record = ApprovalRecord(
        **decision.model_dump(),
        approved_by="reviewer",
        approved_at=datetime(2026, 10, 17, tzinfo=timezone.utc),
    )
    assert ApprovalRecord.model_validate(record.model_dump(mode="json")) == record
    assert record.model_dump(mode="json")["acknowledge_party_roles"] is True
    assert record.model_dump(mode="json")["approved_by"] == "reviewer"


@pytest.mark.asyncio
async def test_legacy_publication_does_not_add_role_requirements(
    repository: AsyncMock, actor: AgreementActor
) -> None:
    repository.get_version.return_value = _version(_draft(roles=False))
    validator = _RoleValidator("party_roles_ambiguous")
    await AgreementMasterService(repository, party_role_validator=validator).approve(
        actor=actor, agreement_id="agreement-1", version_number=4, decision=_decision()
    )
    assert validator.calls == []
    repository.approve.assert_awaited_once()
    assert "acknowledge_party_roles" not in repository.approve.await_args.kwargs[
        "decision"
    ].model_dump(mode="json")


@pytest.mark.asyncio
async def test_legacy_draft_cannot_claim_a_party_review_it_does_not_contain(
    repository: AsyncMock, actor: AgreementActor
) -> None:
    repository.get_version.return_value = _version(_draft(roles=False))
    await AgreementMasterService(repository).approve(
        actor=actor, agreement_id="agreement-1", version_number=4, decision=_decision(roles=True)
    )
    assert "acknowledge_party_roles" not in repository.approve.await_args.kwargs[
        "decision"
    ].model_dump(mode="json")


@pytest.mark.asyncio
async def test_generic_warning_acknowledgement_cannot_replace_explicit_role_review(
    repository: AsyncMock, actor: AgreementActor
) -> None:
    validator = _RoleValidator("party_roles_review_required")
    with pytest.raises(AgreementMasterError) as caught:
        await AgreementMasterService(repository, party_role_validator=validator).approve(
            actor=actor,
            agreement_id="agreement-1",
            version_number=4,
            decision=_decision(warnings=True),
        )
    assert caught.value.code == "invalid_approval"
    assert "party" in str(caught.value).lower()
    repository.approve.assert_not_awaited()


@pytest.mark.asyncio
async def test_separate_role_acknowledgement_is_persisted_for_valid_metadata(
    repository: AsyncMock, actor: AgreementActor
) -> None:
    validator = _RoleValidator("party_roles_review_required")
    await AgreementMasterService(repository, party_role_validator=validator).approve(
        actor=actor, agreement_id="agreement-1", version_number=4, decision=_decision(roles=True)
    )
    assert len(validator.calls) == 1
    saved = repository.approve.await_args.kwargs["decision"]
    assert saved.model_dump(mode="json")["acknowledge_party_roles"] is True
    assert saved.acknowledge_extraction_warnings is False


@pytest.mark.parametrize(
    "code",
    [
        "party_vendor_mismatch",
        "party_roles_ambiguous",
        "party_evidence_missing",
        "party_role_conflict",
        "party_name_unverified",
        "party_role_unverified",
        "party_principals_conflict",
    ],
)
@pytest.mark.asyncio
async def test_all_acknowledgements_cannot_bypass_blocking_role_validation(
    code: str, repository: AsyncMock, actor: AgreementActor
) -> None:
    validator = _RoleValidator("party_roles_review_required", code)
    with pytest.raises(AgreementMasterError) as caught:
        await AgreementMasterService(repository, party_role_validator=validator).approve(
            actor=actor,
            agreement_id="agreement-1",
            version_number=4,
            decision=_decision(roles=True, warnings=True),
        )
    assert caught.value.code == "invalid_approval"
    repository.approve.assert_not_awaited()


@pytest.mark.asyncio
async def test_role_review_does_not_acknowledge_other_extraction_warnings(
    repository: AsyncMock, actor: AgreementActor
) -> None:
    repository.get_version.return_value = _version(_draft(warnings=True))
    validator = _RoleValidator("party_roles_review_required")
    with pytest.raises(AgreementMasterError) as caught:
        await AgreementMasterService(repository, party_role_validator=validator).approve(
            actor=actor,
            agreement_id="agreement-1",
            version_number=4,
            decision=_decision(roles=True),
        )
    assert caught.value.code == "invalid_approval"
    assert "warnings" in str(caught.value).lower()
    repository.approve.assert_not_awaited()


@pytest.mark.asyncio
async def test_only_evidence_from_declared_source_documents_reaches_role_validator(
    repository: AsyncMock, actor: AgreementActor
) -> None:
    draft = _draft()
    unrelated = draft.evidence[0].model_copy(update={"document_id": "unrelated-source"})
    # A custom repository adapter is still scoped defensively at the service boundary.
    repository.get_version.return_value = _version().model_copy(
        update={"draft": draft.model_copy(update={"evidence": (*draft.evidence, unrelated)})}
    )
    validator = _RoleValidator("party_roles_review_required")
    await AgreementMasterService(repository, party_role_validator=validator).approve(
        actor=actor, agreement_id="agreement-1", version_number=4, decision=_decision(roles=True)
    )
    assert validator.calls[0][1] == (draft.evidence[0].evidence,)


@pytest.mark.asyncio
async def test_saved_role_metadata_cannot_be_removed_by_revision(
    repository: AsyncMock, actor: AgreementActor
) -> None:
    with pytest.raises(AgreementMasterError) as caught:
        await AgreementMasterService(repository).revise(
            actor=actor,
            agreement_id="agreement-1",
            expected_version=4,
            draft=_draft(roles=False),
        )
    assert caught.value.code == "invalid_agreement"
    assert "party" in str(caught.value).lower()
    repository.append.assert_not_awaited()


@pytest.mark.asyncio
async def test_legacy_revision_can_opt_into_roles_without_publishing_it(
    repository: AsyncMock, actor: AgreementActor
) -> None:
    repository.get_version.return_value = _version(_draft(roles=False))
    revised = _draft()
    await AgreementMasterService(repository).revise(
        actor=actor, agreement_id="agreement-1", expected_version=4, draft=revised
    )
    assert repository.append.await_args.kwargs["draft"] == revised
    repository.approve.assert_not_awaited()


@pytest.mark.asyncio
async def test_default_validator_blocks_tenant_selected_as_supplier(
    repository: AsyncMock, actor: AgreementActor
) -> None:
    draft = _draft()
    changed = draft.model_copy(
        update={"terms": draft.terms.model_copy(update={"vendor_name": "Example Tenant"})}
    )
    repository.get_version.return_value = _version(changed)
    with pytest.raises(AgreementMasterError) as caught:
        await AgreementMasterService(repository).approve(
            actor=actor,
            agreement_id="agreement-1",
            version_number=4,
            decision=_decision(roles=True, warnings=True),
        )
    assert caught.value.code == "invalid_approval"
    repository.approve.assert_not_awaited()


@pytest.mark.asyncio
async def test_default_validator_accepts_evidenced_roles_only_with_separate_review(
    repository: AsyncMock, actor: AgreementActor
) -> None:
    draft = _draft()
    base = "/extensions/party_roles/parties"
    evidence = tuple(
        AgreementEvidence(
            document_id="source-1",
            evidence=FieldEvidence(field_path=path, source_ids=("p2",), quote=quote),
        )
        for path, quote in (
            (f"{base}/0/name", "Example Owner"),
            (f"{base}/0/source_role", "LESSOR"),
            (f"{base}/1/name", "Example Tenant"),
            (f"{base}/1/source_role", "LESSEE"),
        )
    )
    repository.get_version.return_value = _version(draft.model_copy(update={"evidence": evidence}))
    await AgreementMasterService(repository).approve(
        actor=actor, agreement_id="agreement-1", version_number=4, decision=_decision(roles=True)
    )
    repository.approve.assert_awaited_once()
    assert repository.approve.await_args.kwargs["decision"].acknowledge_party_roles is True
