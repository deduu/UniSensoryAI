"""Generic agent-orchestration framework.

This package provides reusable primitives (tools, agents, orchestrator
strategies) decoupled from any specific application. ``src.chat`` is the
first consumer; ``src.policy`` will migrate over time.

Layered structure:

- ``interfaces`` — ABCs and Protocols every primitive must satisfy.
- ``models``     — frozen Pydantic data classes that flow between them.
- ``strategies`` — pluggable orchestration patterns (single, router, pipeline,
  parallel).
- ``tools``      — built-in tools (web search, content fetcher, ...).
- ``middleware`` — cross-cutting concerns (circuit breaker, retry, ...).
"""
