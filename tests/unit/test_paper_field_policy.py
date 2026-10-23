"""Tenant policy changes share one effective configuration with the matching engine."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from src.paper.contracts import AgreementActor
from src.paper.errors import AgreementMasterError
from src.paper.field_policy.repository import BaseFieldPolicyRepository
from src.paper.field_policy.request import UpdateFieldPolicyRequest
from src.paper.field_policy.service import FieldPolicyService
from src.paper.field_policy.version import FieldPolicyVersion
from src.paper.readiness.requirement import FieldRequirement
from src.paper.reconciliation.fingerprints import policy_fingerprint
from src.paper.reconciliation.settings import ReconciliationSettings
from tests.unit.test_paper_case_workflow import _Setup
from tests.unit.test_paper_case_workflow import setup as invoice_case_fixture

invoice_case_setup = invoice_case_fixture


def requirement(mode: str = "optional") -> FieldRequirement:
    return FieldRequirement.model_validate(
        {
            "role": "rent_invoice",
            "field": "bank_account",
            "requirement": mode,
            "reason": "Reviewed company requirement",
        }
    )


@pytest.mark.asyncio
async def test_default_catalog_preserves_base_and_lists_all_four_roles() -> None:
    repository = AsyncMock(spec=BaseFieldPolicyRepository)
    repository.get_latest.return_value = None
    base = ReconciliationSettings()
    service = FieldPolicyService(repository, base)
    actor = AgreementActor(tenant_id="tenant-a", user_id="reader")
    assert await service.effective(tenant_id=actor.tenant_id) == base
    result = await service.read(actor=actor)
    assert result.revision == 0 and result.can_edit is False
    assert result.updated_at is None and result.policy_version == base.policy_version
    assert {item.role for item in result.requirements} == {
        "rent_invoice",
        "tax_invoice",
        "utility_statement",
        "supporting_document",
    }
    assert (
        next(item for item in result.requirements if item.field == "bank_account").requirement
        == "required"
    )


@pytest.mark.asyncio
async def test_override_changes_effective_policy_and_binds_complete_base_configuration() -> None:
    repository = AsyncMock(spec=BaseFieldPolicyRepository)
    repository.get_latest.return_value = FieldPolicyVersion(
        tenant_id="tenant-a",
        revision=2,
        requirements=(requirement(),),
        updated_by="reviewer",
        updated_at=datetime.now(timezone.utc),
    )
    base = ReconciliationSettings()
    effective = await FieldPolicyService(repository, base).effective(tenant_id="tenant-a")
    assert effective.field_requirements == (requirement(),)
    assert effective.enabled_rules == base.enabled_rules
    assert effective.required_documents == base.required_documents
    assert policy_fingerprint(effective) != policy_fingerprint(base)
    changed_base = ReconciliationSettings(amount_tolerance="1.00")
    changed = await FieldPolicyService(repository, changed_base).effective(tenant_id="tenant-a")
    assert changed.policy_version != effective.policy_version
    result = await FieldPolicyService(repository, base).read(
        actor=AgreementActor(tenant_id="tenant-a", user_id="reader", can_approve=True)
    )
    assert result.revision == 2 and result.can_edit
    assert result.updated_by == "reviewer"


@pytest.mark.asyncio
async def test_write_requires_trusted_authority_before_repository_call() -> None:
    repository = AsyncMock(spec=BaseFieldPolicyRepository)
    service = FieldPolicyService(repository, ReconciliationSettings())
    with pytest.raises(AgreementMasterError) as error:
        await service.update(
            actor=AgreementActor(tenant_id="tenant-a", user_id="reader"),
            request=UpdateFieldPolicyRequest(expected_revision=0, requirements=(requirement(),)),
        )
    assert error.value.code == "forbidden"
    repository.append.assert_not_awaited()


@pytest.mark.parametrize(
    "payload",
    [
        {"expected_revision": True, "requirements": []},
        {"expected_revision": -1, "requirements": []},
        {"expected_revision": 2147483647, "requirements": []},
        {"expected_revision": 0, "requirements": [requirement().model_dump()] * 2},
        {
            "expected_revision": 0,
            "requirements": [
                {
                    "role": "rent_invoice",
                    "field": "extensions",
                    "requirement": "required",
                    "reason": "Unsupported",
                }
            ],
        },
        {"expected_revision": 0, "requirements": [], "can_edit": True},
    ],
)
def test_request_rejects_invalid_or_untrusted_configuration(payload: object) -> None:
    with pytest.raises(ValidationError):
        UpdateFieldPolicyRequest.model_validate(payload)


@pytest.mark.asyncio
async def test_storage_timeout_has_explicit_error() -> None:
    repository = AsyncMock(spec=BaseFieldPolicyRepository)
    repository.get_latest.side_effect = TimeoutError
    with pytest.raises(AgreementMasterError) as error:
        await FieldPolicyService(repository, ReconciliationSettings()).effective(
            tenant_id="tenant-a"
        )
    assert error.value.code == "timeout"


@pytest.mark.asyncio
async def test_tenant_replacement_preserves_explicit_host_requirements() -> None:
    repository = AsyncMock(spec=BaseFieldPolicyRepository)
    base_requirement = FieldRequirement(
        role="tax_invoice",
        field="tax_invoice_number",
        requirement="required",
        reason="Explicit host control",
    )
    base = ReconciliationSettings(field_requirements=(base_requirement,))
    repository.get_latest.return_value = FieldPolicyVersion(
        tenant_id="tenant-a",
        revision=1,
        requirements=(requirement(),),
        updated_by="reviewer",
        updated_at=datetime.now(timezone.utc),
    )
    effective = await FieldPolicyService(repository, base).effective(tenant_id="tenant-a")
    assert effective.field_requirements == (base_requirement, requirement())
    repository.get_latest.return_value = repository.get_latest.return_value.model_copy(
        update={"revision": 2, "requirements": ()}
    )
    reset = await FieldPolicyService(repository, base).effective(tenant_id="tenant-a")
    assert reset.field_requirements == base.field_requirements
    assert reset.policy_version != base.policy_version


@pytest.mark.asyncio
async def test_saved_policy_change_blocks_approval_of_an_old_assessment(
    invoice_case_setup: _Setup,
) -> None:
    from src.paper.reconciliation.contracts import APDecision
    from src.paper.reconciliation.engine import ReconciliationEngine
    from src.paper.reconciliation.workflow import InvoiceCaseService

    _, cases, master, actor, case = invoice_case_setup
    policies = AsyncMock(spec=BaseFieldPolicyRepository)
    policies.get_latest.return_value = FieldPolicyVersion(
        tenant_id=actor.tenant_id,
        revision=1,
        requirements=(requirement(),),
        updated_by=actor.user_id,
        updated_at=datetime.now(timezone.utc),
    )
    settings = await FieldPolicyService(policies, ReconciliationSettings()).effective(
        tenant_id=actor.tenant_id
    )
    service = InvoiceCaseService(
        cases, master=master, engine=ReconciliationEngine(settings), settings=settings
    )
    with pytest.raises(AgreementMasterError) as error:
        await service.decide_case(
            actor=actor,
            case_id=case.case_id,
            expected_version=case.version_number,
            decision=APDecision(action="approve", reason="Reviewed saved result"),
        )
    assert error.value.code == "conflict"
    cases.decide.assert_not_awaited()
