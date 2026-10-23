"""Explainable role checks that never turn source occurrence into semantic approval."""

from collections.abc import Sequence

from src.extraction.contracts import DocumentResult, ExtractionIssue, FieldEvidence
from src.paper.schemas.party_roles import PartyRoles
from src.paper.schemas.rent_agreement import RentAgreementSchema

from .normalization import contains_text, normalized_text
from .settings import PartyRoleSettings
from .validator import BasePartyRoleValidator

_BASE = "/extensions/party_roles"


class DeterministicPartyRoleValidator(BasePartyRoleValidator):
    """Check explicit role labels, unique principals, supplier mapping and citations."""

    def __init__(self, settings: PartyRoleSettings | None = None) -> None:
        """Inject a host lexicon without constructing inference or storage dependencies."""
        self._settings = PartyRoleSettings.model_validate(settings or PartyRoleSettings())

    def validate(
        self,
        terms: RentAgreementSchema,
        evidence: Sequence[FieldEvidence],
        *,
        document: DocumentResult | None = None,
    ) -> tuple[ExtractionIssue, ...]:
        """Validate role candidates and their literal evidence without changing values.

        Args:
            terms: Source-derived candidates containing optional typed party metadata.
            evidence: References already scoped by the host to the intended document.
            document: Optional extracted blocks; omitted for retained-draft review.

        Returns:
            Safe diagnostics. Only ``party_roles_review_required`` is informational;
            every other issue describes an unresolved input, role or evidence gap.
            Even a clean result requires human interpretation of representation
            chains and operative clauses before approval.
        """
        terms = RentAgreementSchema.model_validate(terms)
        refs = tuple(FieldEvidence.model_validate(item) for item in evidence)
        metadata = terms.extensions.get("party_roles")
        if metadata is None:
            return (
                ExtractionIssue(
                    code="party_roles_missing",
                    message="Extract and review separate landlord and tenant principals before publication.",
                    field_path=_BASE,
                ),
            )
        roles = PartyRoles.model_validate(metadata)
        warnings: list[ExtractionIssue] = []
        seen: set[tuple[str, str]] = set()

        def warn(code: str, message: str, path: str) -> None:
            if (code, path) not in seen:
                warnings.append(ExtractionIssue(code=code, message=message, field_path=path))
                seen.add((code, path))

        warn(
            "party_roles_review_required",
            "Review legal principals, operative roles and all representation intermediaries. Literal source support and a connected candidate chain are traceability, not independent semantic verification or proof that the chain is complete.",
            _BASE,
        )
        source_text: dict[str, str] | None = None
        duplicate_ids: set[str] = set()
        if document is not None:
            document = DocumentResult.model_validate(document)
            source_text = {}
            for page in document.pages:
                for block in page.text_blocks:
                    if block.block_id in source_text:
                        duplicate_ids.add(block.block_id)
                    source_text[block.block_id] = block.text
                for asset in page.images:
                    if asset.description:
                        if asset.asset_id in source_text:
                            duplicate_ids.add(asset.asset_id)
                        source_text[asset.asset_id] = asset.description

        def support(paths: tuple[str, ...]) -> tuple[FieldEvidence, ...]:
            selected = tuple(item for item in refs if item.field_path in paths)
            if not selected:
                warn(
                    "party_evidence_missing",
                    "This party attribute lacks retained field-specific source support.",
                    paths[0],
                )
                return ()
            valid: list[FieldEvidence] = []
            for item in selected:
                if source_text is not None:
                    quote = " ".join(item.quote.split())
                    texts = [source_text.get(identity) for identity in item.source_ids]
                    if (
                        any(identity in duplicate_ids for identity in item.source_ids)
                        or any(text is None for text in texts)
                        or not any(
                            quote in " ".join(text.split()) for text in texts if text is not None
                        )
                    ):
                        warn(
                            "party_evidence_invalid",
                            "A party citation cannot be verified against its original source block.",
                            item.field_path,
                        )
                        continue
                valid.append(item)
            return tuple(valid)

        landlords = [party for party in roles.parties if party.role == "landlord"]
        tenants = [party for party in roles.parties if party.role == "tenant"]
        if len(landlords) != 1 or len(tenants) != 1:
            warn(
                "party_roles_ambiguous",
                "Exactly one resolved landlord and one resolved tenant principal are required for this agreement mapping; review additional or unknown candidates.",
                _BASE,
            )
        if len(landlords) == 1 and len(tenants) == 1:
            landlord, tenant = landlords[0], tenants[0]
            if (
                landlord.name is not None
                and tenant.name is not None
                and normalized_text(landlord.name) == normalized_text(tenant.name)
            ):
                warn(
                    "party_principals_conflict",
                    "Landlord and tenant candidates identify the same principal; review their legal roles.",
                    _BASE,
                )
        if terms.vendor_name is None:
            warn(
                "party_vendor_missing",
                "The landlord supplier mapping is unresolved.",
                "/vendor_name",
            )
        elif len(landlords) == 1 and (
            landlords[0].name is None
            or not normalized_text(terms.vendor_name)
            or normalized_text(terms.vendor_name) != normalized_text(landlords[0].name)
        ):
            warn(
                "party_vendor_mismatch",
                "The supplier candidate disagrees with the extracted landlord principal. Preserve both candidates and resolve the role before approval.",
                "/vendor_name",
            )

        labels = {
            "landlord": {normalized_text(label) for label in self._settings.landlord_labels},
            "tenant": {normalized_text(label) for label in self._settings.tenant_labels},
        }
        for index, party in enumerate(roles.parties):
            path = f"{_BASE}/parties/{index}"
            if party.name is None or not normalized_text(party.name):
                warn(
                    "party_name_unverified",
                    "The legal principal name is unresolved.",
                    path + "/name",
                )
            else:
                names = support((path + "/name",))
                if not any(contains_text(item.quote, party.name) for item in names):
                    warn(
                        "party_name_unverified",
                        "Retained citations do not establish the complete extracted principal name.",
                        path + "/name",
                    )
            targets: dict[str, str] = {}
            for representative_index, representative in enumerate(party.representatives):
                representative_path = f"{path}/representatives/{representative_index}"
                key = normalized_text(representative.name)
                if not key or key in targets:
                    warn(
                        "party_representation_ambiguous",
                        "Representative candidates contain an empty or repeated normalized identity; review each distinct representation step.",
                        representative_path + "/name",
                    )
                targets[key] = normalized_text(representative.represents or "")
                attributes = (
                    ("name", representative.name),
                    ("represents", representative.represents),
                    ("capacity", representative.capacity),
                )
                for attribute, value in attributes:
                    if value is None:
                        continue
                    attribute_path = f"{representative_path}/{attribute}"
                    attribute_refs = support((attribute_path,))
                    if not any(contains_text(item.quote, value) for item in attribute_refs):
                        warn(
                            "party_representation_unverified",
                            "Retained citations do not establish this complete representation attribute; preserve unknown values and review the operative chain.",
                            attribute_path,
                        )
            principal = normalized_text(party.name or "")
            for representative_index, representative in enumerate(party.representatives):
                current = normalized_text(representative.represents or "")
                visited = {normalized_text(representative.name)}
                while not principal or current != principal:
                    if not current or current in visited or current not in targets:
                        warn(
                            "party_representation_unverified",
                            "The representation candidate does not resolve through known intermediaries to its party principal. Review omitted links, unknown principals or cycles without inferring them.",
                            f"{path}/representatives/{representative_index}/represents",
                        )
                        break
                    visited.add(current)
                    current = targets[current]
            if party.role not in labels:
                if party.role == "unknown":
                    warn(
                        "party_role_unverified",
                        "The principal's contractual role remains unresolved.",
                        path + "/role",
                    )
                continue
            label = normalized_text(party.source_role or "")
            expected = labels[party.role]
            other = labels["tenant" if party.role == "landlord" else "landlord"]
            if label in other:
                warn(
                    "party_role_conflict",
                    "The source role designation conflicts with the assigned contractual role.",
                    path + "/role",
                )
            elif label not in expected:
                warn(
                    "party_role_unverified",
                    "The source role designation is unknown or outside the configured role lexicon. Review it without inferring a role from party order.",
                    path + "/source_role",
                )
            role_refs = support((path + "/source_role", path + "/role"))
            if party.source_role is None or not any(
                contains_text(item.quote, party.source_role) for item in role_refs
            ):
                warn(
                    "party_role_unverified",
                    "Retained citations do not establish the extracted source role designation.",
                    path + "/source_role",
                )
        return tuple(warnings)


def validate_party_roles(
    terms: RentAgreementSchema,
    evidence: Sequence[FieldEvidence],
    document: DocumentResult | None = None,
    *,
    settings: PartyRoleSettings | None = None,
) -> tuple[ExtractionIssue, ...]:
    """Validate party roles with injectable host labels and no source mutation.

    Args:
        terms: Source-derived terms with optional party-role metadata.
        evidence: Same-document field references qualified by the embedding host.
        document: Optional extracted source for literal citation verification.
        settings: Optional externally configured deterministic role lexicon.

    Returns:
        Safe role diagnostics, retaining explicit human review even with citations.
    """
    return DeterministicPartyRoleValidator(settings).validate(terms, evidence, document=document)
