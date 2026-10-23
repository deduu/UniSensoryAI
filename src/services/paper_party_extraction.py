"""PAPER party enrichment through an injected, provider-neutral extraction service."""

import structlog
from pydantic import ValidationError

from src.extraction.contracts import (
    DocumentResult,
    ExtractionIssue,
    ExtractionOptions,
    FieldExtractionResult,
)
from src.extraction.service import ExtractionService
from src.paper.parties import (
    BasePartyRoleValidator,
    DeterministicPartyRoleValidator,
    get_party_roles_schema,
)
from src.paper.parties.extractor import BaseAgreementPartyExtractor
from src.paper.schemas.rent_agreement import RentAgreementSchema

_logger = structlog.get_logger(__name__)


def _party_path(path: str) -> bool:
    return (
        path == "/vendor_name"
        or path == "/extensions/party_roles"
        or path.startswith("/extensions/party_roles/")
    )


def unresolved_party_roles(fields: FieldExtractionResult) -> FieldExtractionResult:
    """Retain values with unresolved roles after failure, preventing legacy approval.

    Args:
        fields: Base candidates whose source history must remain unchanged.

    Returns:
        A new candidate with explicit unresolved roles and a safe warning.
    """
    data = dict(fields.data)
    existing = data.get("extensions")
    extensions = dict(existing) if isinstance(existing, dict) else {}
    data["extensions"] = {**extensions, "party_roles": {"version": "1", "parties": []}}
    return FieldExtractionResult(
        schema_id=fields.schema_id,
        schema_version=fields.schema_version,
        data=data,
        evidence=fields.evidence,
        model_ids=fields.model_ids,
        warnings=fields.warnings
        + (
            ExtractionIssue(
                code="party_roles_extraction_failed",
                message="Party roles could not be extracted. Retained values require correction and source review before approval.",
                field_path="/extensions/party_roles",
            ),
        ),
    )


class AgreementPartyExtractor(BaseAgreementPartyExtractor):
    """Re-extract principals and representation chains, then validate source roles."""

    def __init__(
        self,
        service: ExtractionService,
        *,
        validator: BasePartyRoleValidator | None = None,
    ) -> None:
        """Inject model orchestration and pure validation; never construct a model.

        Args:
            service: Existing shared extraction service owned by the host.
            validator: Optional host-specific role policy.
        """
        self._service = service
        self._validator = validator or DeterministicPartyRoleValidator()

    async def enrich(
        self,
        document: DocumentResult,
        fields: FieldExtractionResult,
        options: ExtractionOptions,
    ) -> FieldExtractionResult:
        """Return a targeted correction with citations and unresolved-review markers.

        Args:
            document: Full extracted source; party clauses can span several pages.
            fields: New candidate fields; historical artifacts remain unchanged.
            options: Shared model profile and extraction deadline.

        Returns:
            A distinct candidate, retaining all unrelated data and previous warnings.
        """
        original = fields.model_dump(mode="json", exclude={"status"})
        data = dict(fields.data)
        existing = data.get("extensions")
        extensions = dict(existing) if isinstance(existing, dict) else {}
        try:
            targeted = await self._service.extract_fields(
                document,
                get_party_roles_schema(),
                model_profile=options.fields_profile,
                timeout_seconds=options.timeout_seconds,
            )
            roles = targeted.data.get("extensions")
            if not isinstance(roles, dict) or "party_roles" not in roles:
                raise ValueError("Missing typed role metadata.")
            candidate = {
                **data,
                "vendor_name": targeted.data.get("vendor_name"),
                "extensions": {**extensions, "party_roles": roles["party_roles"]},
            }
            terms = RentAgreementSchema.model_validate(candidate)
            evidence = tuple(
                item for item in fields.evidence if not _party_path(item.field_path)
            ) + tuple(
                item
                for item in targeted.evidence
                if _party_path(item.field_path)
                and item.field_path != "/extensions/party_roles/version"
            )
            # Protocol metadata is not a fact that can be quoted from the PDF.
            targeted_warnings = tuple(
                item
                for item in targeted.warnings
                if item.field_path != "/extensions/party_roles/version"
            )
            warnings = (
                fields.warnings
                + targeted_warnings
                + self._validator.validate(terms, evidence, document=document)
            )
            return FieldExtractionResult(
                **{
                    **original,
                    "data": candidate,
                    "evidence": evidence,
                    "warnings": warnings,
                    "model_ids": tuple(dict.fromkeys(fields.model_ids + targeted.model_ids)),
                }
            )
        except Exception as error:  # noqa: BLE001 - retain source without provider details
            _logger.warning(
                "paper_party_enrichment_incomplete",
                error_type=(
                    type(error).__name__
                    if isinstance(error, (ValueError, ValidationError))
                    else "extraction_failed"
                ),
            )
            return unresolved_party_roles(fields)
