"""Tenant-scoped, sequential contract discovery and exact-reference revalidation."""

import asyncio
import unicodedata
from collections.abc import Awaitable
from typing import Literal, TypeVar

from src.paper.contracts import AgreementActor, AgreementLookup, AgreementVersion
from src.paper.errors import AgreementMasterError
from src.paper.service import AgreementMasterService

from .candidate import AssociationCandidate
from .candidates import AssociationCandidates
from .deterministic_matcher import DeterministicAssociationMatcher
from .matcher import BaseAssociationMatcher
from .period import association_period
from .query import AssociationQuery
from .selection import AssociationSelection
from .settings import AssociationSettings

_T = TypeVar("_T")
_Coverage = Literal["verified", "unverified", "conflicting"]


def _same_version(left: AgreementVersion | None, right: AgreementVersion) -> bool:
    return (
        left is not None
        and left.tenant_id == right.tenant_id
        and left.agreement_id == right.agreement_id
        and left.version_number == right.version_number
        and left.identity == right.identity
        and left.approval is not None
    )


class AssociationService:
    """Suggest contracts and revalidate proposed links without writing source fields."""

    def __init__(
        self,
        master: AgreementMasterService,
        *,
        settings: AssociationSettings | None = None,
        matcher: BaseAssociationMatcher | None = None,
    ) -> None:
        """Inject master reads and a replaceable model-independent matcher.

        Args:
            master: Tenant-scoped agreement lifecycle service, owned by the host.
            settings: Host-owned policy and read bounds.
            matcher: Optional pure ranking adapter.
        """
        self._master = master
        self._settings = AssociationSettings.model_validate(settings or AssociationSettings())
        self._matcher = matcher or DeterministicAssociationMatcher(self._settings)

    @property
    def settings(self) -> AssociationSettings:
        """Return immutable host policy for trusted confirmation provenance."""
        return self._settings

    async def _run(self, operation: Awaitable[_T]) -> _T:
        try:
            return await asyncio.wait_for(operation, self._settings.timeout_seconds)
        except asyncio.TimeoutError:
            raise AgreementMasterError(
                "timeout", "Contract association exceeded its deadline."
            ) from None

    async def _references(
        self, actor: AgreementActor, query: AssociationQuery, reference: AgreementVersion
    ) -> tuple[AgreementVersion | None, AgreementVersion | None]:
        first, last = association_period(query.invoice, query.review_context)
        start = end = None
        if first is not None:
            start = await self._master.find_approved(
                actor=actor, lookup=AgreementLookup(identity=reference.identity, as_of=first)
            )
        if last is not None:
            end = await self._master.find_approved(
                actor=actor, lookup=AgreementLookup(identity=reference.identity, as_of=last)
            )
        return start, end

    @staticmethod
    def _coverage(
        query: AssociationQuery,
        reference: AgreementVersion,
        start: AgreementVersion | None,
        end: AgreementVersion | None,
    ) -> _Coverage:
        first, last = association_period(query.invoice, query.review_context)
        if first is not None and (
            not _same_version(start, reference)
            or not reference.draft.effective_from <= first <= reference.draft.effective_to
            or (
                start is not None
                and not start.draft.effective_from <= first <= start.draft.effective_to
            )
        ):
            return "conflicting"
        if last is not None and (
            not _same_version(end, reference)
            or not reference.draft.effective_from <= last <= reference.draft.effective_to
            or (end is not None and not end.draft.effective_from <= last <= end.draft.effective_to)
        ):
            return "conflicting"
        return "verified" if first is not None and last is not None else "unverified"

    async def _history(
        self, actor: AgreementActor, catalog: AgreementVersion
    ) -> tuple[AgreementVersion | None, bool]:
        size = self._settings.history_page_limit
        for page in range(self._settings.max_history_pages):
            versions = await self._master.list_versions(
                actor=actor,
                agreement_id=catalog.agreement_id,
                limit=size,
                offset=page * size,
            )
            for version in versions:
                if (
                    version.tenant_id == actor.tenant_id
                    and version.agreement_id == catalog.agreement_id
                    and version.identity == catalog.identity
                    and version.approval is not None
                ):
                    return version, False
            if len(versions) < size:
                return None, False
        return None, True

    async def suggest(
        self, *, actor: AgreementActor, query: AssociationQuery
    ) -> AssociationCandidates:
        """Read a bounded catalog batch and rank approved manual alternatives.

        Args:
            actor: Trusted tenant and reviewer supplied by the host.
            query: Source invoice, optional allocation, and catalog batch bounds.

        Returns:
            Suggestions with explicit ambiguity, evidence signals, and continuation.
        """
        actor = AgreementActor.model_validate(actor)
        query = AssociationQuery.model_validate(query)
        return await self._run(self._suggest(actor, query))

    async def _suggest(
        self, actor: AgreementActor, query: AssociationQuery
    ) -> AssociationCandidates:
        catalog = await self._master.list_agreements(
            actor=actor, limit=query.limit, offset=query.offset
        )
        candidates: list[AssociationCandidate] = []
        seen: set[str] = set()
        history_incomplete = False
        for current in catalog:
            if current.tenant_id != actor.tenant_id or current.agreement_id in seen:
                continue
            seen.add(current.agreement_id)
            start, end = await self._references(actor, query, current)
            reference = next(
                (
                    item
                    for item in (start, end)
                    if item is not None
                    and item.tenant_id == actor.tenant_id
                    and item.agreement_id == current.agreement_id
                    and item.identity == current.identity
                    and item.approval is not None
                ),
                None,
            )
            if reference is None:
                reference, incomplete = await self._history(actor, current)
                history_incomplete = history_incomplete or incomplete
            if reference is None:
                continue
            candidate = self._matcher.evaluate(
                query.invoice,
                reference,
                review_context=query.review_context,
                coverage=self._coverage(query, reference, start, end),
            )
            search = unicodedata.normalize("NFKC", query.search or "").casefold().strip()
            haystack = " ".join(
                str(value or "")
                for value in (
                    candidate.identity.contract_number,
                    candidate.identity.vendor_id,
                    candidate.identity.store_id,
                    candidate.vendor_name,
                    candidate.location,
                )
            )
            if not search or search in unicodedata.normalize("NFKC", haystack).casefold():
                candidates.append(candidate)
        candidates.sort(
            key=lambda item: (
                not item.relevant,
                -item.rank,
                not item.eligible,
                item.identity.contract_number,
                item.agreement_id,
                -item.version_number,
            )
        )
        relevant = sum(item.relevant and item.eligible for item in candidates)
        has_more = len(catalog) >= query.limit
        return AssociationCandidates(
            candidates=tuple(candidates),
            state="ambiguous" if relevant > 1 else "suggestions" if relevant else "no_match",
            offset=query.offset,
            limit=query.limit,
            next_offset=query.offset + len(catalog) if has_more else None,
            has_more=has_more,
            exhaustive=query.offset == 0 and not has_more and not history_incomplete,
            history_incomplete=history_incomplete,
            policy_id=self._settings.policy_id,
            policy_version=self._settings.policy_version,
        )

    async def candidate(
        self,
        *,
        actor: AgreementActor,
        query: AssociationQuery,
        selection: AssociationSelection,
    ) -> AssociationCandidate:
        """Revalidate one exact selection before the host records confirmation.

        Args:
            actor: Trusted tenant and reviewer.
            query: Current source invoice and separate reviewed allocation.
            selection: Exact selected version and human reason.

        Returns:
            Fresh comparison signals; unapproved records are ineligible.

        Raises:
            AgreementMasterError: The record is absent, foreign, or conflicts with
                the approved version effective on a known billing boundary.
        """
        actor = AgreementActor.model_validate(actor)
        query = AssociationQuery.model_validate(query)
        selection = AssociationSelection.model_validate(
            selection.model_dump(include={"agreement_id", "version_number", "reason"})
        )
        return await self._run(self._candidate(actor, query, selection))

    async def _candidate(
        self,
        actor: AgreementActor,
        query: AssociationQuery,
        selection: AssociationSelection,
    ) -> AssociationCandidate:
        reference = await self._master.get_version(
            actor=actor,
            agreement_id=selection.agreement_id,
            version_number=selection.version_number,
        )
        if (
            reference.tenant_id != actor.tenant_id
            or reference.agreement_id != selection.agreement_id
            or reference.version_number != selection.version_number
        ):
            raise AgreementMasterError("not_found", "Selected agreement was not found.")
        start, end = await self._references(actor, query, reference)
        coverage = self._coverage(query, reference, start, end)
        if coverage == "conflicting":
            raise AgreementMasterError(
                "conflict",
                "The selected agreement version does not cover the current billing period; "
                "refresh candidates.",
            )
        return self._matcher.evaluate(
            query.invoice, reference, review_context=query.review_context, coverage=coverage
        )
