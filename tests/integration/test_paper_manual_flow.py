"""Manual PAPER cases exercise real authorization, rules, storage, and AP review."""

import asyncio
import json
from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth import UserContext, get_user_context
from src.api.paper_case_routes import router as case_router
from src.api.paper_routes import get_paper_db
from src.api.paper_routes import router as agreement_router
from src.db.models.user import User
from tests.integration.test_paper_invoice_cases import db  # noqa: F401
from tests.unit.test_paper_case_workflow import package, reference

_Client = tuple[httpx.AsyncClient, dict[str, UserContext]]


@pytest.mark.asyncio
async def test_installment_withholding_full_flow_requires_evidence_and_explicit_ap_review(
    client: _Client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    http, _ = client
    root = Path(__file__).resolve().parents[2]
    monkeypatch.setenv(
        "PAPER_RECONCILIATION_CONFIG_PATH", str(root / "configs/paper_reconciliation.yaml")
    )
    agreement = json.loads(
        await asyncio.to_thread(
            (root / "examples/paper/installment_agreement.json").read_text, encoding="utf8"
        )
    )
    invoice = json.loads(
        await asyncio.to_thread(
            (root / "examples/paper/installment_invoice_package.json").read_text, encoding="utf8"
        )
    )
    created_master = await http.post("/v1/paper/agreements", json=agreement)
    assert created_master.status_code == 201
    agreement_id = created_master.json()["agreement_id"]
    approved = await http.post(
        f"/v1/paper/agreements/{agreement_id}/versions/1/approval",
        json={
            "classification": "psak73",
            "rule_set_id": "synthetic-reviewed-policy",
            "rule_set_version": "1",
            "reason": "Explicit synthetic approval for software test only",
        },
    )
    assert approved.status_code == 200
    incomplete = {**invoice, "supporting_documents": []}
    first = await http.post("/v1/paper/cases", json=incomplete)
    assert first.status_code == 201
    case_id = first.json()["case_id"]
    assert first.json()["status"] == "incomplete"
    denied = await http.post(
        f"/v1/paper/cases/{case_id}/versions/1/decision",
        json={"action": "approve", "reason": "Cannot bypass missing withholding evidence"},
    )
    assert denied.status_code == 422
    corrected = await http.post(
        f"/v1/paper/cases/{case_id}/versions",
        json={"expected_version": 1, "package": invoice},
    )
    assert corrected.status_code == 201
    result = corrected.json()
    assert result["status"] == "needs_review"
    assert result["package"]["invoice"]["fields"]["service_period_start"] is None
    codes = sorted({finding["code"] for finding in result["assessment"]["findings"]})
    assert codes == [
        "approved_installment_allocation",
        "installment_conditions_review",
        "source_pricing_discrepancy",
    ]
    no_ack = await http.post(
        f"/v1/paper/cases/{case_id}/versions/2/decision",
        json={"action": "approve", "reason": "Review flags must be acknowledged explicitly"},
    )
    assert no_ack.status_code == 422
    decision = await http.post(
        f"/v1/paper/cases/{case_id}/versions/2/decision",
        json={
            "action": "approve",
            "reason": "Reviewed synthetic allocation, prerequisites and retained discrepancy",
            "override_codes": codes,
        },
    )
    assert decision.status_code == 200
    assert decision.json()["status"] == "approved"
    invoice["invoice"]["fields"]["invoice_number"] = "DEMO-DIFFERENT-INVOICE"
    invoice["supporting_documents"][0]["fields"]["invoice_number"] = "DEMO-DIFFERENT-INVOICE"
    invoice["supporting_documents"][0]["fields"]["reference_number"] = "DEMO-DIFFERENT-CERTIFICATE"
    duplicate = await http.post("/v1/paper/cases", json=invoice)
    assert duplicate.status_code == 201
    assert duplicate.json()["status"] == "duplicate"
    assert duplicate.json()["duplicate_of"] == case_id


@pytest_asyncio.fixture
async def client(
    db: AsyncSession,  # noqa: F811 - pytest injects the imported fixture by name.
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[_Client]:
    monkeypatch.delenv("PAPER_CONFIG_PATH", raising=False)
    monkeypatch.delenv("PAPER_RECONCILIATION_CONFIG_PATH", raising=False)
    db.add_all(
        [
            User(
                id="reviewer-a",
                tenant_id="tenant-a",
                email="a@example.test",
                oauth_provider="test",
                oauth_subject="a",
                role="accountant",
            ),
            User(
                id="member-b",
                tenant_id="tenant-b",
                email="b@example.test",
                oauth_provider="test",
                oauth_subject="b",
                role="member",
            ),
        ]
    )
    await db.commit()
    app = FastAPI()
    app.include_router(agreement_router)
    app.include_router(case_router)
    identity = {"current": UserContext(user_id="reviewer-a", tenant_id="tenant-a")}

    async def session() -> AsyncIterator[AsyncSession]:
        try:
            yield db
        except Exception:
            await db.rollback()
            raise

    async def user() -> UserContext:
        return identity["current"]

    app.dependency_overrides[get_paper_db] = session
    app.dependency_overrides[get_user_context] = user
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://paper.test"
    ) as http:
        yield http, identity


async def _approved_master(http: httpx.AsyncClient) -> str:
    master = reference()
    response = await http.post(
        "/v1/paper/agreements",
        json={
            "identity": master.identity.model_dump(),
            "draft": master.draft.model_dump(mode="json"),
        },
    )
    assert response.status_code == 201
    agreement_id = response.json()["agreement_id"]
    published = await http.post(
        f"/v1/paper/agreements/{agreement_id}/versions/1/approval",
        json={
            "classification": "non_psak73",
            "rule_set_id": "test-policy",
            "rule_set_version": "1",
            "reason": "Reviewed synthetic agreement",
        },
    )
    assert published.status_code == 200
    return agreement_id


@pytest.mark.asyncio
async def test_matched_case_duplicate_and_ap_history_are_durable(client: _Client) -> None:
    http, identity = client
    await _approved_master(http)
    created = await http.post("/v1/paper/cases", json=package().model_dump(mode="json"))
    assert created.status_code == 201
    case = created.json()
    assert case["status"] == "matched"
    assert case["assessment"]["agreement_reference"]["classification"] == "non_psak73"
    approved = await http.post(
        f"/v1/paper/cases/{case['case_id']}/versions/1/decision",
        json={
            "action": "approve",
            "reason": "Reviewed complete package",
        },
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"
    assert approved.json()["decision"]["decided_by"] == "reviewer-a"
    history = await http.get(f"/v1/paper/cases/{case['case_id']}/versions")
    assert history.json()[0] == approved.json()
    duplicate = await http.post("/v1/paper/cases", json=package().model_dump(mode="json"))
    assert duplicate.status_code == 201
    assert duplicate.json()["status"] == "duplicate"
    assert duplicate.json()["duplicate_of"] == case["case_id"]
    cannot_approve = await http.post(
        f"/v1/paper/cases/{duplicate.json()['case_id']}/versions/1/decision",
        json={
            "action": "approve",
            "reason": "Attempted duplicate approval",
        },
    )
    assert cannot_approve.status_code == 422
    listing = await http.get("/v1/paper/cases")
    assert len(listing.json()) == 2
    identity["current"] = UserContext(user_id="member-b", tenant_id="tenant-b")
    hidden = await http.get(f"/v1/paper/cases/{case['case_id']}/versions/1")
    assert hidden.status_code == 404
    assert (await http.get("/v1/paper/cases")).json() == []


@pytest.mark.asyncio
async def test_missing_documents_override_and_stale_agreement_have_distinct_outcomes(
    client: _Client,
) -> None:
    http, _ = client
    agreement_id = await _approved_master(http)
    incomplete_body = package().model_dump(mode="json")
    incomplete_body["tax_invoices"] = []
    created = await http.post("/v1/paper/cases", json=incomplete_body)
    case_id = created.json()["case_id"]
    assert created.json()["status"] == "incomplete"
    blocked = await http.post(
        f"/v1/paper/cases/{case_id}/versions/1/decision",
        json={"action": "approve", "reason": "Reviewed"},
    )
    assert blocked.status_code == 422
    revision = await http.post(
        f"/v1/paper/cases/{case_id}/versions",
        json={
            "expected_version": 1,
            "package": package().model_dump(mode="json"),
        },
    )
    assert revision.status_code == 201 and revision.json()["status"] == "matched"
    amended = await http.post(
        f"/v1/paper/agreements/{agreement_id}/versions",
        json={
            "expected_version": 1,
            "draft": reference().draft.model_dump(mode="json"),
        },
    )
    assert amended.status_code == 201
    published = await http.post(
        f"/v1/paper/agreements/{agreement_id}/versions/2/approval",
        json={
            "classification": "non_psak73",
            "rule_set_id": "test-policy",
            "rule_set_version": "2",
            "reason": "Reviewed amendment",
        },
    )
    assert published.status_code == 200
    stale = await http.post(
        f"/v1/paper/cases/{case_id}/versions/2/decision",
        json={"action": "approve", "reason": "Reviewed old case"},
    )
    assert stale.status_code == 409
    refreshed = await http.post(
        f"/v1/paper/cases/{case_id}/versions",
        json={
            "expected_version": 2,
            "package": package().model_dump(mode="json"),
        },
    )
    assert refreshed.status_code == 201
    assert refreshed.json()["assessment"]["agreement_reference"]["version_number"] == 2
    stale_case = await http.post(
        f"/v1/paper/cases/{case_id}/versions/2/decision",
        json={"action": "approve", "reason": "Reviewed superseded version"},
    )
    assert stale_case.status_code == 409
    matched = await http.post(
        f"/v1/paper/cases/{case_id}/versions/3/decision",
        json={"action": "approve", "reason": "Reviewed refreshed case"},
    )
    assert matched.status_code == 200

    mismatch_body = package().model_dump(mode="json")
    mismatch_body["invoice"]["fields"]["invoice_number"] = "INV-OVERRIDE"
    mismatch_body["tax_invoices"][0]["fields"]["invoice_number"] = "INV-OVERRIDE"
    mismatch_body["invoice"]["fields"]["bank_account"] = "009999"
    mismatch = await http.post("/v1/paper/cases", json=mismatch_body)
    assert mismatch.json()["status"] == "mismatched"
    override = await http.post(
        f"/v1/paper/cases/{mismatch.json()['case_id']}/versions/1/decision",
        json={
            "action": "approve",
            "reason": "Beneficiary verified independently",
            "override_codes": ["bank_mismatch"],
        },
    )
    assert override.status_code == 200
    assert override.json()["decision"]["override_codes"] == ["bank_mismatch"]


@pytest.mark.asyncio
async def test_swagger_example_payloads_follow_real_case_routes(client: _Client) -> None:
    http, _ = client
    examples = Path(__file__).resolve().parents[2] / "examples/paper"
    agreement = json.loads((examples / "agreement.json").read_text(encoding="utf-8"))
    invoice = json.loads((examples / "invoice_package.json").read_text(encoding="utf-8"))
    revised = json.loads((examples / "case_revision.json").read_text(encoding="utf-8"))
    created = await http.post("/v1/paper/agreements", json=agreement)
    assert created.status_code == 201
    published = await http.post(
        f"/v1/paper/agreements/{created.json()['agreement_id']}/versions/1/approval",
        json={
            "classification": "non_psak73",
            "rule_set_id": "demo-accounting-policy",
            "rule_set_version": "1",
            "reason": "Reviewed synthetic UI test agreement",
        },
    )
    assert published.status_code == 200
    matched = await http.post("/v1/paper/cases", json=invoice)
    assert matched.status_code == 201 and matched.json()["status"] == "matched"
    approved = await http.post(
        f"/v1/paper/cases/{matched.json()['case_id']}/versions/1/decision",
        json={
            "action": "approve",
            "reason": "Reviewed complete synthetic invoice package",
        },
    )
    assert approved.status_code == 200 and approved.json()["status"] == "approved"
    incomplete = {**revised["package"], "tax_invoices": []}
    missing = await http.post("/v1/paper/cases", json=incomplete)
    assert missing.status_code == 201 and missing.json()["status"] == "incomplete"
    fixed = await http.post(f"/v1/paper/cases/{missing.json()['case_id']}/versions", json=revised)
    assert fixed.status_code == 201 and fixed.json()["status"] == "matched"
