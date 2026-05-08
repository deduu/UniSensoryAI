"""Tests for the LLM-based policy conflict agent."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from src.policy.agents import LLMPolicyConflictAgent
from src.policy.llm_comparator import LLMComparator, LLMComparatorConfig
from src.policy.models import PolicyClause, PolicyFinding, PolicyReviewContext


def _make_context(**overrides) -> PolicyReviewContext:
    defaults = dict(
        job_id="job-1",
        policy_document_id="doc-1",
        policy_filename="proposal.pdf",
        policy_text=(
            "Engineers may use any third-party AI service to accelerate work. "
            "Customer support agents may paste customer chat transcripts into ChatGPT."
        ),
        reference_documents=[
            PolicyClause(
                text="Vendor AI services must be on the approved-vendor list.",
                source="database",
                document_id="ref-1",
                filename="acme_existing.pdf",
            ),
            PolicyClause(
                text="Customer chat transcripts may not be sent to external AI services.",
                source="database",
                document_id="ref-1",
                filename="acme_existing.pdf",
            ),
        ],
        include_web_search=False,
        include_trusted_sources=False,
    )
    defaults.update(overrides)
    return PolicyReviewContext(**defaults)


@pytest.mark.asyncio
async def test_skips_when_api_key_missing(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    agent = LLMPolicyConflictAgent()

    result = await agent.review(_make_context())

    assert result.agent_name == "llm_policy_conflict"
    assert result.findings == []
    assert result.metadata.get("skipped") is True
    assert any("ANTHROPIC_API_KEY" in note for note in result.notes)


@pytest.mark.asyncio
async def test_skips_when_disabled_in_config():
    comparator = LLMComparator(
        config=LLMComparatorConfig(enabled=False, api_key="anything")
    )
    agent = LLMPolicyConflictAgent(comparator=comparator)

    result = await agent.review(_make_context())

    assert result.metadata.get("skipped") is True
    assert any("disabled" in note.lower() for note in result.notes)


@pytest.mark.asyncio
async def test_returns_findings_from_comparator():
    comparator = LLMComparator(
        config=LLMComparatorConfig(enabled=True, api_key="sk-test")
    )
    fake_findings = [
        PolicyFinding(
            title="Conflict with approved-vendor rule",
            description=(
                "The proposal allows any third-party AI service, but the existing "
                "policy requires services to be on the approved-vendor list."
            ),
            severity="high",
            source="synthesis",
            clauses=[
                PolicyClause(
                    text="Engineers may use any third-party AI service.",
                    source="uploaded_document",
                    document_id="doc-1",
                    filename="proposal.pdf",
                ),
                PolicyClause(
                    text="Vendor AI services must be on the approved-vendor list.",
                    source="database",
                    document_id="ref-1",
                    filename="acme_existing.pdf",
                ),
            ],
            recommendation="Narrow scope or update the approved-vendor list.",
            confidence=0.85,
            metadata={"conflict_reason": "approved-vendor rule overridden"},
        )
    ]
    comparator.compare = AsyncMock(return_value=fake_findings)
    agent = LLMPolicyConflictAgent(comparator=comparator)

    result = await agent.review(_make_context())

    assert result.agent_name == "llm_policy_conflict"
    assert len(result.findings) == 1
    finding = result.findings[0]
    assert finding.source == "synthesis"
    assert finding.severity == "high"
    assert "approved-vendor" in finding.description
    assert result.metadata.get("skipped") is not True
    assert result.metadata.get("findings_returned") == 1
    comparator.compare.assert_awaited_once()


@pytest.mark.asyncio
async def test_handles_comparator_error_gracefully():
    comparator = LLMComparator(
        config=LLMComparatorConfig(enabled=True, api_key="sk-test")
    )
    comparator.compare = AsyncMock(side_effect=RuntimeError("API timeout"))
    agent = LLMPolicyConflictAgent(comparator=comparator)

    result = await agent.review(_make_context())

    assert result.findings == []
    assert any("API timeout" in note for note in result.notes)
    assert result.metadata.get("error")


@pytest.mark.asyncio
async def test_skips_when_no_proposal_clauses(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    comparator = LLMComparator(
        config=LLMComparatorConfig(enabled=True, api_key="sk-test")
    )
    comparator.compare = AsyncMock(return_value=[])
    agent = LLMPolicyConflictAgent(comparator=comparator)

    context = _make_context(policy_text="   ")
    result = await agent.review(context)

    assert result.metadata.get("skipped") is True
    comparator.compare.assert_not_called()


@pytest.mark.asyncio
async def test_skips_when_no_references_available():
    comparator = LLMComparator(
        config=LLMComparatorConfig(enabled=True, api_key="sk-test")
    )
    comparator.compare = AsyncMock(return_value=[])
    agent = LLMPolicyConflictAgent(comparator=comparator)

    context = _make_context(
        reference_documents=[],
        include_web_search=False,
        include_trusted_sources=False,
    )
    result = await agent.review(context)

    assert result.metadata.get("skipped") is True
    assert any("reference" in note.lower() for note in result.notes)
    comparator.compare.assert_not_called()


@pytest.mark.asyncio
async def test_parses_structured_response_from_anthropic_client():
    """The comparator should call the Anthropic SDK and parse a JSON response."""

    class _Block:
        def __init__(self, text: str) -> None:
            self.type = "text"
            self.text = text

    class _Response:
        def __init__(self, payload: str) -> None:
            self.content = [_Block(payload)]
            self.usage = type(
                "Usage",
                (),
                {
                    "cache_creation_input_tokens": 0,
                    "cache_read_input_tokens": 0,
                    "input_tokens": 100,
                    "output_tokens": 50,
                },
            )()

    payload = (
        '{"findings": [{'
        '"title": "Approved-vendor conflict", '
        '"description": "Proposal permits unvetted services; existing policy requires approval.", '
        '"severity": "high", '
        '"proposal_clause": "Engineers may use any third-party AI service.", '
        '"reference_clause": "Vendor AI services must be on the approved-vendor list.", '
        '"reference_source": "database", '
        '"reference_filename": "acme_existing.pdf", '
        '"recommendation": "Update vendor list or narrow scope.", '
        '"confidence": 0.9'
        "}]}"
    )

    fake_client = AsyncMock()
    fake_client.messages = AsyncMock()
    fake_client.messages.create = AsyncMock(return_value=_Response(payload))

    comparator = LLMComparator(
        config=LLMComparatorConfig(enabled=True, api_key="sk-test"),
        client=fake_client,
    )

    findings = await comparator.compare(
        proposal_text="Engineers may use any third-party AI service.",
        reference_clauses=[
            PolicyClause(
                text="Vendor AI services must be on the approved-vendor list.",
                source="database",
                document_id="ref-1",
                filename="acme_existing.pdf",
            )
        ],
        proposal_document_id="doc-1",
        proposal_filename="proposal.pdf",
        focus=None,
    )

    assert len(findings) == 1
    assert findings[0].severity == "high"
    assert findings[0].source == "synthesis"
    assert findings[0].confidence == pytest.approx(0.9)
    assert len(findings[0].clauses) == 2
    fake_client.messages.create.assert_awaited_once()
    call_kwargs = fake_client.messages.create.await_args.kwargs
    assert call_kwargs["model"] == "claude-opus-4-7"


@pytest.mark.asyncio
async def test_handles_malformed_llm_response():
    class _Block:
        def __init__(self, text: str) -> None:
            self.type = "text"
            self.text = text

    class _Response:
        def __init__(self, payload: str) -> None:
            self.content = [_Block(payload)]
            self.usage = type(
                "Usage",
                (),
                {
                    "cache_creation_input_tokens": 0,
                    "cache_read_input_tokens": 0,
                    "input_tokens": 1,
                    "output_tokens": 1,
                },
            )()

    fake_client = AsyncMock()
    fake_client.messages = AsyncMock()
    fake_client.messages.create = AsyncMock(
        return_value=_Response("not valid json at all")
    )

    comparator = LLMComparator(
        config=LLMComparatorConfig(enabled=True, api_key="sk-test"),
        client=fake_client,
    )

    findings = await comparator.compare(
        proposal_text="Engineers may use any third-party AI service.",
        reference_clauses=[
            PolicyClause(
                text="Approved vendors only.",
                source="database",
                document_id="ref-1",
                filename="ref.pdf",
            )
        ],
        proposal_document_id="doc-1",
        proposal_filename="proposal.pdf",
        focus=None,
    )

    assert findings == []
