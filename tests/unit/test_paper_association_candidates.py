"""Contract suggestions rank evidence without assigning source identifiers."""

from datetime import date, datetime, timezone
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from src.paper.association.confirmation import AssociationConfirmation
from src.paper.association.deterministic_matcher import DeterministicAssociationMatcher
from src.paper.association.fingerprints import invoice_fingerprint
from src.paper.association.query import AssociationQuery
from src.paper.association.selection import AssociationSelection
from src.paper.association.service import AssociationService
from src.paper.association.settings import AssociationSettings, load_association_settings
from src.paper.contracts import (
    AgreementActor,
    AgreementDraft,
    AgreementIdentity,
    AgreementVersion,
    ApprovalRecord,
)
from src.paper.errors import AgreementMasterError
from src.paper.reconciliation.contracts.rent_invoice_document import RentInvoiceDocument
from src.paper.reconciliation.contracts.review_context import ReconciliationReviewContext
from src.paper.schemas import RentAgreementSchema, RentInvoiceSchema
from src.paper.service import AgreementMasterService


def invoice(**fields: object) -> RentInvoiceDocument:
    """Return a source invoice without assigned canonical identifiers."""
    return RentInvoiceDocument(
        source_document_id="invoice-source",
        fields=RentInvoiceSchema.model_validate(
            {"vendor_name": "Supplier A", "location": "Jalan Merdeka 1", **fields}
        ),
    )


def agreement(
    *, version: int = 1, approved: bool = True, tenant: str = "tenant-1", **terms: object
) -> AgreementVersion:
    """Return one immutable approved reference with its source terms."""
    return AgreementVersion(
        agreement_id="agreement-1",
        tenant_id=tenant,
        version_number=version,
        identity=AgreementIdentity(vendor_id="V-1", store_id="S-1", contract_number="RA-1"),
        draft=AgreementDraft(
            terms=RentAgreementSchema.model_validate(
                {"vendor_name": "Supplier A", "location": "Jalan Merdeka 1", **terms}
            ),
            effective_from=date(2026, 1, 1),
            effective_to=date(2026, 12, 31),
            source_document_ids=("contract-source",),
            change_reason="Contract reviewed",
        ),
        created_by="author",
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        approval=(
            ApprovalRecord(
                classification="non_psak73",
                rule_set_id="manual",
                rule_set_version="1",
                reason="Reviewed original",
                approved_by="reviewer",
                approved_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
            )
            if approved
            else None
        ),
    )


def actor() -> AgreementActor:
    return AgreementActor(tenant_id="tenant-1", user_id="reviewer")


def master() -> AsyncMock:
    result = AsyncMock(spec=AgreementMasterService)
    result.list_agreements.return_value = (agreement(),)
    result.list_versions.return_value = (agreement(),)
    result.find_approved.return_value = agreement()
    result.get_version.return_value = agreement()
    return result


def allocation() -> ReconciliationReviewContext:
    return ReconciliationReviewContext(
        allocation_start=date(2026, 6, 1),
        allocation_end=date(2026, 6, 30),
        reason="Advance rent coverage reviewed",
        source_document_ids=("invoice-source",),
    )


def test_matcher_keeps_source_ids_missing_and_ranks_explicit_references() -> None:
    source = invoice(contract_number="RA-1")
    before = source.model_dump(mode="json")
    candidate = DeterministicAssociationMatcher().evaluate(source, agreement())
    signals = {item.field: item for item in candidate.signals}
    assert candidate.relevant
    assert signals["contract_number"].status == "matched"
    assert signals["vendor_id"].status == "missing"
    assert signals["vendor_name"].status == "matched"
    assert signals["contract_number"].invoice_paths == ("/contract_number",)
    assert source.model_dump(mode="json") == before
    assert source.fields.vendor_id is None


def test_normalized_names_are_supporting_signals_without_id_mapping() -> None:
    candidate = DeterministicAssociationMatcher().evaluate(
        invoice(vendor_name=" supplier  A ", location="JALAN MERDEKA 1"), agreement()
    )
    signals = {item.field: item for item in candidate.signals}
    assert signals["vendor_name"].status == "matched"
    assert signals["vendor_name"].strength == "supporting"
    assert signals["vendor_id"].invoice_value is None


def test_bank_and_amount_alone_never_make_candidate_relevant() -> None:
    source = invoice(vendor_name=None, location=None, subtotal="100", bank_account="00123")
    candidate = DeterministicAssociationMatcher().evaluate(
        source, agreement(fixed_rent="100", bank_account="00123")
    )
    assert not candidate.relevant
    assert candidate.rank == 0


def test_explicit_conflict_is_visible_and_drafts_ineligible() -> None:
    matcher = DeterministicAssociationMatcher()
    candidate = matcher.evaluate(invoice(contract_number="RA-OTHER"), agreement())
    signal = next(item for item in candidate.signals if item.field == "contract_number")
    assert signal.status == "conflicting"
    assert not matcher.evaluate(invoice(), agreement(approved=False)).eligible
    assert not matcher.evaluate(invoice(), agreement(), coverage="conflicting").eligible


def test_fingerprint_binds_values_evidence_and_reviewed_allocation() -> None:
    source = invoice()
    assert invoice_fingerprint(source) != invoice_fingerprint(invoice(contract_number="RA-1"))
    assert invoice_fingerprint(source) != invoice_fingerprint(source, allocation())
    assert invoice_fingerprint(source) == invoice_fingerprint(source.model_copy(deep=True))


def test_empty_normalized_names_and_out_of_window_dates_never_match() -> None:
    matcher = DeterministicAssociationMatcher()
    candidate = matcher.evaluate(
        invoice(vendor_name="...", location=None), agreement(vendor_name="--")
    )
    assert not candidate.relevant
    candidate = matcher.evaluate(
        invoice(service_period_start="2027-01-01", service_period_end="2027-01-31"),
        agreement(),
        coverage="verified",
    )
    assert candidate.coverage == "conflicting"
    assert not candidate.eligible


@pytest.mark.asyncio
async def test_suggestions_resolve_older_approved_version_hidden_by_draft() -> None:
    dependency = master()
    dependency.list_agreements.return_value = (agreement(version=2, approved=False),)
    result = await AssociationService(dependency).suggest(
        actor=actor(), query=AssociationQuery(invoice=invoice())
    )
    assert result.candidates[0].version_number == 1
    assert result.candidates[0].coverage == "unverified"
    assert result.candidates[0].eligible
    assert result.state == "suggestions"
    assert result.requires_confirmation


@pytest.mark.asyncio
async def test_dated_candidates_pin_same_approved_version_at_both_boundaries() -> None:
    dependency = master()
    source = invoice(service_period_start="2026-06-01", service_period_end="2026-06-30")
    result = await AssociationService(dependency).suggest(
        actor=actor(), query=AssociationQuery(invoice=source)
    )
    assert result.candidates[0].coverage == "verified"
    assert dependency.find_approved.await_count == 2
    assert dependency.find_approved.call_args_list[0].kwargs["lookup"].as_of == date(2026, 6, 1)
    dependency.list_versions.assert_not_awaited()


@pytest.mark.asyncio
async def test_review_allocation_is_separate_and_partial_source_period_is_not_filled() -> None:
    dependency = master()
    service = AssociationService(dependency)
    await service.suggest(
        actor=actor(), query=AssociationQuery(invoice=invoice(), review_context=allocation())
    )
    assert dependency.find_approved.await_count == 2
    dependency.find_approved.reset_mock()
    result = await service.suggest(
        actor=actor(),
        query=AssociationQuery(
            invoice=invoice(service_period_start="2026-06-01"), review_context=allocation()
        ),
    )
    assert result.candidates[0].coverage == "unverified"
    assert all(
        call.kwargs["lookup"].as_of != date(2026, 6, 30)
        for call in dependency.find_approved.call_args_list
    )


@pytest.mark.asyncio
async def test_expired_or_split_authority_is_visible_but_not_eligible() -> None:
    dependency = master()
    source = invoice(service_period_start="2026-06-01", service_period_end="2026-06-30")
    dependency.find_approved.return_value = None
    result = await AssociationService(dependency).suggest(
        actor=actor(), query=AssociationQuery(invoice=source)
    )
    assert result.candidates[0].coverage == "conflicting"
    assert not result.candidates[0].eligible
    dependency.find_approved.side_effect = (agreement(), agreement(version=2))
    result = await AssociationService(dependency).suggest(
        actor=actor(), query=AssociationQuery(invoice=source)
    )
    assert not result.candidates[0].eligible


@pytest.mark.asyncio
async def test_foreign_tenant_catalog_or_history_never_exposes_candidate() -> None:
    dependency = master()
    dependency.list_agreements.return_value = (agreement(tenant="foreign"),)
    result = await AssociationService(dependency).suggest(
        actor=actor(), query=AssociationQuery(invoice=invoice())
    )
    assert not result.candidates
    dependency.list_versions.assert_not_awaited()
    dependency.list_agreements.return_value = (agreement(),)
    dependency.list_versions.return_value = (agreement(tenant="foreign"),)
    result = await AssociationService(dependency).suggest(
        actor=actor(), query=AssociationQuery(invoice=invoice())
    )
    assert not result.candidates


@pytest.mark.asyncio
async def test_manual_nonmatching_candidates_remain_available_and_batch_is_explicit() -> None:
    dependency = master()
    source = invoice(vendor_name=None, location=None)
    result = await AssociationService(dependency).suggest(
        actor=actor(), query=AssociationQuery(invoice=source, limit=1)
    )
    assert len(result.candidates) == 1
    assert not result.candidates[0].relevant
    assert result.state == "no_match"
    assert result.has_more
    assert result.next_offset == 1
    assert not result.exhaustive


@pytest.mark.asyncio
async def test_two_relevant_contracts_are_ambiguous_without_automatic_selection() -> None:
    dependency = master()
    other = agreement().model_copy(update={"agreement_id": "agreement-2"})
    dependency.list_agreements.return_value = (agreement(), other)
    dependency.list_versions.side_effect = ((agreement(),), (other,))
    result = await AssociationService(dependency).suggest(
        actor=actor(), query=AssociationQuery(invoice=invoice())
    )
    assert result.state == "ambiguous"
    assert len(result.candidates) == 2
    assert result.requires_confirmation


@pytest.mark.asyncio
async def test_exact_candidate_revalidates_effective_reference() -> None:
    dependency = master()
    query = AssociationQuery(
        invoice=invoice(service_period_start="2026-06-01", service_period_end="2026-06-30")
    )
    selection = AssociationSelection(
        agreement_id="agreement-1", version_number=1, reason="Original contract checked"
    )
    candidate = await AssociationService(dependency).candidate(
        actor=actor(), query=query, selection=selection
    )
    assert candidate.eligible
    dependency.find_approved.return_value = agreement(version=2)
    with pytest.raises(AgreementMasterError, match="does not cover"):
        await AssociationService(dependency).candidate(
            actor=actor(), query=query, selection=selection
        )


@pytest.mark.asyncio
async def test_exact_foreign_or_draft_selection_cannot_be_confirmed() -> None:
    dependency = master()
    selection = AssociationSelection(
        agreement_id="agreement-1", version_number=1, reason="Reviewed"
    )
    dependency.get_version.return_value = agreement(tenant="foreign")
    with pytest.raises(AgreementMasterError):
        await AssociationService(dependency).candidate(
            actor=actor(), query=AssociationQuery(invoice=invoice()), selection=selection
        )
    dependency.get_version.return_value = agreement(approved=False)
    result = await AssociationService(dependency).candidate(
        actor=actor(), query=AssociationQuery(invoice=invoice()), selection=selection
    )
    assert not result.eligible


@pytest.mark.asyncio
async def test_saved_confirmation_can_be_revalidated_as_selection() -> None:
    dependency = master()
    source = invoice()
    confirmation = AssociationConfirmation(
        agreement_id="agreement-1",
        version_number=1,
        reason="Original contract checked",
        confirmed_by="reviewer",
        confirmed_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
        invoice_fingerprint=invoice_fingerprint(source),
        policy_id="paper.contract_association",
        policy_version="1",
    )
    candidate = await AssociationService(dependency).candidate(
        actor=actor(), query=AssociationQuery(invoice=source), selection=confirmation
    )
    assert candidate.eligible
    assert confirmation.confirmed_at == datetime(2026, 6, 1, tzinfo=timezone.utc)


@pytest.mark.asyncio
async def test_unsearched_history_is_reported_as_incomplete() -> None:
    dependency = master()
    draft = agreement(version=2, approved=False)
    dependency.list_agreements.return_value = (draft,)
    dependency.list_versions.return_value = (draft,)
    settings = AssociationSettings(history_page_limit=1, max_history_pages=1)
    result = await AssociationService(dependency, settings=settings).suggest(
        actor=actor(), query=AssociationQuery(invoice=invoice())
    )
    assert not result.candidates
    assert result.history_incomplete
    assert not result.exhaustive


@pytest.mark.asyncio
async def test_settings_load_and_search_are_host_owned() -> None:
    settings = await load_association_settings()
    assert settings.policy_id
    dependency = master()
    result = await AssociationService(dependency, settings=settings).suggest(
        actor=actor(), query=AssociationQuery(invoice=invoice(), search="not found")
    )
    assert not result.candidates
    with pytest.raises(ValidationError):
        AssociationQuery(invoice=invoice(), limit=101)
    with pytest.raises(ValidationError):
        AssociationSettings(identity_weight=-1)
