"""Isolated SQLite persistence and HTTP integration for tenant matching policy."""

from collections.abc import AsyncIterator

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth import UserContext, get_user_context
from src.api.paper_case_routes import (
    get_base_reconciliation_settings,
    get_reconciliation_settings,
    review_router,
)
from src.api.paper_field_policy_routes import router
from src.api.paper_routes import get_paper_db
from src.db.models.paper_field_policy_version import PaperFieldPolicyVersion
from src.db.models.user import User
from src.paper.contracts import AgreementActor
from src.paper.errors import AgreementMasterError
from src.paper.field_policy.request import UpdateFieldPolicyRequest
from src.paper.field_policy.service import FieldPolicyService
from src.paper.readiness.requirement import FieldRequirement
from src.paper.reconciliation.settings import ReconciliationSettings
from src.services.paper_field_policy_repository import SqlAlchemyFieldPolicyRepository
from tests.integration.test_paper_agreement_master import db as agreement_db

db = agreement_db


def _actor(tenant: str = "tenant-a") -> AgreementActor:
    return AgreementActor(tenant_id=tenant, user_id="reviewer", can_approve=True)


def _request(revision: int = 0, mode: str = "optional") -> UpdateFieldPolicyRequest:
    return UpdateFieldPolicyRequest.model_validate(
        {
            "expected_revision": revision,
            "requirements": [
                {
                    "role": "rent_invoice",
                    "field": "bank_account",
                    "requirement": mode,
                    "reason": "Reviewed company requirement",
                }
            ],
        }
    )


@pytest.mark.asyncio
async def test_policy_is_durable_tenant_scoped_versioned_and_conflict_safe(
    db: AsyncSession,
) -> None:
    base = ReconciliationSettings()
    service = FieldPolicyService(SqlAlchemyFieldPolicyRepository(db), base)
    first = await service.update(actor=_actor(), request=_request())
    await db.commit()
    assert first.revision == 1 and first.updated_by == "reviewer"
    assert first.updated_at is not None and first.updated_at.tzinfo is not None
    second = await service.update(actor=_actor(), request=_request(1, "required"))
    await db.commit()
    assert second.revision == 2 and second.policy_version != first.policy_version
    history = (
        await db.scalars(select(PaperFieldPolicyVersion).order_by(PaperFieldPolicyVersion.revision))
    ).all()
    assert [row.requirements[0]["requirement"] for row in history] == ["optional", "required"]
    retained_time = history[0].updated_at
    with pytest.raises(AgreementMasterError) as error:
        await service.update(actor=_actor(), request=_request(1))
    assert error.value.code == "conflict"
    with pytest.raises(AgreementMasterError) as duplicate:
        await service.update(actor=_actor(), request=_request(0))
    assert duplicate.value.code == "conflict"
    assert (await service.read(actor=_actor())).revision == 2
    assert (await service.read(actor=_actor("tenant-b"))).revision == 0
    assert await service.effective(tenant_id="tenant-b") == base
    assert history[0].updated_at == retained_time
    await db.rollback()
    fresh = FieldPolicyService(SqlAlchemyFieldPolicyRepository(db), base)
    assert (await fresh.read(actor=_actor())).revision == 2


@pytest.mark.asyncio
async def test_policy_write_rolls_back_with_host_transaction_and_history_is_immutable(
    db: AsyncSession,
) -> None:
    service = FieldPolicyService(SqlAlchemyFieldPolicyRepository(db), ReconciliationSettings())
    await service.update(actor=_actor(), request=_request())
    await db.rollback()
    assert (await service.read(actor=_actor())).revision == 0
    await service.update(actor=_actor(), request=_request())
    await db.commit()
    row = (await db.scalars(select(PaperFieldPolicyVersion))).one()
    row.updated_by = "rewritten reviewer"
    with pytest.raises(ValueError, match="immutable"):
        await db.flush()
    await db.rollback()


@pytest.mark.asyncio
async def test_http_permission_validation_and_effective_policy_match(db: AsyncSession) -> None:
    db.add_all(
        [
            User(
                id="reviewer",
                tenant_id="tenant-a",
                email="reviewer@example.test",
                oauth_provider="test",
                oauth_subject="reviewer",
                role="accountant",
            ),
            User(
                id="member",
                tenant_id="tenant-a",
                email="member@example.test",
                oauth_provider="test",
                oauth_subject="member",
                role="member",
            ),
        ]
    )
    await db.commit()
    app = FastAPI()
    app.include_router(router)
    app.include_router(review_router)
    schema = app.openapi()
    assert set(schema["paths"]["/v1/paper/field-requirements"]) == {"get", "put"}
    assert {"base_requirements", "overrides"}.issubset(
        schema["components"]["schemas"]["FieldPolicyCatalog"]["properties"]
    )
    base = ReconciliationSettings()
    identity = UserContext(user_id="reviewer", tenant_id="tenant-a")

    async def session() -> AsyncIterator[AsyncSession]:
        yield db

    app.dependency_overrides[get_paper_db] = session
    app.dependency_overrides[get_user_context] = lambda: identity
    app.dependency_overrides[get_base_reconciliation_settings] = lambda: base

    @app.get("/effective")
    async def effective_policy() -> dict[str, object]:
        return (await get_reconciliation_settings(user=identity, db=db, base=base)).model_dump(
            mode="json"
        )

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        initial = await client.get("/v1/paper/field-requirements")
        assert initial.status_code == 200 and initial.json()["can_edit"]
        assert initial.json()["revision"] == 0
        saved = await client.put(
            "/v1/paper/field-requirements", json=_request().model_dump(mode="json")
        )
        assert saved.status_code == 200 and saved.json()["revision"] == 1
        current = (await client.get("/effective")).json()
        context = (await client.get("/v1/paper/review-context")).json()
        assert (
            context["policy_version"] == current["policy_version"] == saved.json()["policy_version"]
        )
        assert context["field_requirements"] == current["field_requirements"]
        stale = await client.put(
            "/v1/paper/field-requirements", json=_request().model_dump(mode="json")
        )
        assert stale.status_code == 409
        invalid = await client.put(
            "/v1/paper/field-requirements",
            json={
                "expected_revision": 1,
                "requirements": [
                    {
                        "role": "rent_invoice",
                        "field": "unknown",
                        "requirement": "required",
                        "reason": "bad",
                    }
                ],
            },
        )
        assert invalid.status_code == 422
        identity = UserContext(user_id="member", tenant_id="tenant-a")
        readonly = await client.get("/v1/paper/field-requirements")
        assert readonly.status_code == 200 and readonly.json()["can_edit"] is False
        denied = await client.put(
            "/v1/paper/field-requirements", json=_request(1).model_dump(mode="json")
        )
        assert denied.status_code == 403
        identity = UserContext(user_id="reviewer", tenant_id="tenant-b")
        other = await client.get("/v1/paper/field-requirements")
        assert other.status_code == 200 and other.json()["revision"] == 0
        assert other.json()["can_edit"] is False


@pytest.mark.asyncio
async def test_saved_requirement_drives_readiness_and_engine_without_waiving_coverage(
    db: AsyncSession,
) -> None:
    from tests.unit.test_paper_readiness import _confirmed, _evaluate
    from tests.unit.test_paper_reconciliation import _package

    service = FieldPolicyService(SqlAlchemyFieldPolicyRepository(db), ReconciliationSettings())
    required = FieldRequirement(
        role="rent_invoice", field="due_date", requirement="required", reason="Company control"
    )
    await service.update(
        actor=_actor(),
        request=UpdateFieldPolicyRequest(expected_revision=0, requirements=(required,)),
    )
    settings = await service.effective(tenant_id="tenant-a")
    result, assessment = _evaluate(_confirmed(_package()), settings)
    assert not result.ready
    assert any(item.field_path == "/invoice/fields/due_date" for item in assessment.findings)
    optional_dates = tuple(
        FieldRequirement(
            role="rent_invoice", field=field, requirement="optional", reason="Presence optional"
        )
        for field in ("service_period_start", "service_period_end")
    )
    await service.update(
        actor=_actor(),
        request=UpdateFieldPolicyRequest(expected_revision=1, requirements=optional_dates),
    )
    settings = await service.effective(tenant_id="tenant-a")
    result, assessment = _evaluate(
        _confirmed(_package(service_period_start=None, service_period_end=None)), settings
    )
    assert not result.ready and assessment.outcome == "incomplete"
    assert any(item.kind == "authority" and item.blocking for item in result.checks)


@pytest.mark.asyncio
@pytest.mark.parametrize("required_documents", [("rent_invoice",), ("rent_invoice", "tax_invoice")])
async def test_sparse_catalog_save_preserves_inherited_tax_presence_and_substitution(
    db: AsyncSession, required_documents: tuple[str, ...]
) -> None:
    from src.paper.reconciliation.composition import build_reconciliation_engine
    from tests.unit.test_paper_installment_rules import _agreement, _package

    base = ReconciliationSettings.model_validate(
        {
            "required_documents": required_documents,
            "required_invoice_fields": [
                "invoice_number",
                "currency",
                "subtotal",
                "tax_amount",
                "total",
            ],
            "enabled_rules": ["installments", "withholding"],
            "allow_withholding_without_vat_invoice": True,
        }
    )
    service = FieldPolicyService(SqlAlchemyFieldPolicyRepository(db), base)
    initial = await service.read(actor=_actor())
    assert initial.overrides == () and initial.requirements == initial.base_requirements
    assert any(
        item.role == "tax_invoice" and item.requirement == "required"
        for item in initial.base_requirements
    )
    # The UI sends only changed explicit overrides, not inherited catalog rows.
    saved = await service.update(actor=_actor(), request=_request())
    assert len(saved.overrides) == 1 and saved.overrides[0].role == "rent_invoice"
    effective = await service.effective(tenant_id="tenant-a")
    reference = _agreement()
    result = build_reconciliation_engine(effective).assess(
        _package(), agreement_start=reference, agreement_end=reference, tenant_id="tenant-1"
    )
    assert not any(item.code == "missing_document" for item in result.findings)
    assert effective.required_documents == required_documents
    assert effective.allow_withholding_without_vat_invoice


@pytest.mark.asyncio
async def test_policy_migration_round_trip_on_isolated_database(db: AsyncSession) -> None:
    import importlib.util
    from pathlib import Path

    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy import inspect
    from sqlalchemy.engine import Connection

    path = Path(__file__).parents[2] / "alembic/versions/b9040a7fe213_add_paper_field_policy.py"
    spec = importlib.util.spec_from_file_location("field_policy_migration", path)
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    def cycle(connection: Connection) -> None:
        context = MigrationContext.configure(connection)
        with Operations.context(context):
            migration.downgrade()
            assert "paperfieldpolicies" not in inspect(connection).get_table_names()
            migration.upgrade()
            assert "paperfieldpolicyversions" in inspect(connection).get_table_names()
            assert "paperdocumentdrafts" in inspect(connection).get_table_names()

    connection = await db.connection()
    await connection.run_sync(cycle)
    assert (
        await FieldPolicyService(
            SqlAlchemyFieldPolicyRepository(db), ReconciliationSettings()
        ).read(actor=_actor())
    ).revision == 0
