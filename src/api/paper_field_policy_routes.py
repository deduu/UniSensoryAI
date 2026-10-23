"""Authorized tenant settings for shared document match field requirements."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.paper_case_routes import get_base_reconciliation_settings, get_invoice_actor
from src.api.paper_routes import _commit, _domain_errors, _rate_limit, get_paper_db
from src.paper.contracts import AgreementActor
from src.paper.field_policy.catalog import FieldPolicyCatalog
from src.paper.field_policy.request import UpdateFieldPolicyRequest
from src.paper.field_policy.service import FieldPolicyService
from src.paper.reconciliation.settings import ReconciliationSettings
from src.services.paper_field_policy_repository import SqlAlchemyFieldPolicyRepository

router = APIRouter(prefix="/v1/paper", tags=["paper"], dependencies=[Depends(_rate_limit)])


async def get_field_policy_service(
    db: Annotated[AsyncSession, Depends(get_paper_db)],
    base: Annotated[ReconciliationSettings, Depends(get_base_reconciliation_settings)],
) -> FieldPolicyService:
    """Bind policy storage and deployment configuration in the host transaction.

    Args:
        db: Request-scoped host transaction shared with case operations.
        base: Cached, validated deployment policy.

    Returns:
        Service that resolves and updates tenant field presence requirements.
    """
    return FieldPolicyService(SqlAlchemyFieldPolicyRepository(db), base)


@router.get("/field-requirements", response_model=FieldPolicyCatalog)
async def read_field_requirements(
    actor: Annotated[AgreementActor, Depends(get_invoice_actor)],
    service: Annotated[FieldPolicyService, Depends(get_field_policy_service)],
) -> FieldPolicyCatalog:
    """Read effective requirements and the persisted reviewer's permission.

    Args:
        actor: Host-resolved tenant identity and AP review authority.
        service: Tenant policy service in the request transaction.

    Returns:
        Full effective guidance, host guidance and explicit tenant overrides.
    """
    with _domain_errors():
        return await service.read(actor=actor)


@router.put("/field-requirements", response_model=FieldPolicyCatalog)
async def update_field_requirements(
    body: UpdateFieldPolicyRequest,
    actor: Annotated[AgreementActor, Depends(get_invoice_actor)],
    service: Annotated[FieldPolicyService, Depends(get_field_policy_service)],
    db: Annotated[AsyncSession, Depends(get_paper_db)],
) -> FieldPolicyCatalog:
    """Commit a guarded policy revision without changing historical cases.

    Args:
        body: Complete replacement of explicit tenant overrides and revision guard.
        actor: Host-resolved tenant identity and persisted AP review authority.
        service: Injected async policy lifecycle.
        db: Host transaction to commit before returning success.

    Returns:
        Effective requirements and server-stamped saved revision provenance.
    """
    with _domain_errors():
        result = await service.update(actor=actor, request=body)
        await _commit(db)
        return result
