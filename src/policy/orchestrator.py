"""Parallel orchestration for policy review agents."""

from __future__ import annotations

import asyncio
import time

from .models import (
    BasePolicyReviewAgent,
    PolicyAgentResult,
    PolicyReviewContext,
    PolicyReviewResult,
)


class ParallelPolicyReviewOrchestrator:
    """Run specialized policy review agents concurrently and merge their output."""

    def __init__(
        self,
        agents: list[BasePolicyReviewAgent],
        *,
        timeout_seconds: float = 30.0,
    ) -> None:
        self._agents = agents
        self._timeout_seconds = timeout_seconds

    async def run(self, context: PolicyReviewContext) -> PolicyReviewResult:
        """Execute all agents in parallel and return a merged review."""
        started = time.monotonic()
        tasks = [self._run_agent(agent, context) for agent in self._agents]
        agent_results = await asyncio.gather(*tasks)

        findings = []
        for result in agent_results:
            findings.extend(result.findings)

        findings.sort(key=lambda item: {"high": 0, "medium": 1, "low": 2}[item.severity])
        summary = self._summarize(findings_count=len(findings), agent_results=agent_results)

        return PolicyReviewResult(
            job_id=context.job_id,
            document_id=context.policy_document_id,
            filename=context.policy_filename,
            findings=findings,
            agent_results=agent_results,
            summary=summary,
            metadata={
                "agent_count": len(self._agents),
                "elapsed_ms": int((time.monotonic() - started) * 1000),
            },
        )

    async def _run_agent(
        self,
        agent: BasePolicyReviewAgent,
        context: PolicyReviewContext,
    ) -> PolicyAgentResult:
        try:
            return await asyncio.wait_for(agent.review(context), timeout=self._timeout_seconds)
        except asyncio.TimeoutError:
            return PolicyAgentResult(
                agent_name=agent.name,
                notes=[f"Agent timed out after {self._timeout_seconds:.1f}s."],
                metadata={"timed_out": True},
            )
        except Exception as exc:
            return PolicyAgentResult(
                agent_name=agent.name,
                notes=[f"Agent failed: {exc}"],
                metadata={"error": str(exc)},
            )

    @staticmethod
    def _summarize(
        *,
        findings_count: int,
        agent_results: list[PolicyAgentResult],
    ) -> str:
        high_count = sum(
            1 for result in agent_results for finding in result.findings if finding.severity == "high"
        )
        degraded_count = sum(
            1
            for result in agent_results
            if result.metadata.get("error")
            or result.metadata.get("timed_out")
            or result.metadata.get("degraded")
        )
        if findings_count == 0:
            if degraded_count:
                return (
                    "No contradictions were detected by the successful agents, but "
                    f"{degraded_count} agent(s) had errors or incomplete coverage, so this review is incomplete."
                )
            return "No contradictions or interference risks were detected by the configured agents."
        if high_count:
            summary = f"Detected {findings_count} policy issue(s), including {high_count} high-severity issue(s)."
        else:
            summary = f"Detected {findings_count} potential policy issue(s) for review."
        if degraded_count:
            summary += f" {degraded_count} agent(s) also had errors or incomplete coverage."
        return summary
