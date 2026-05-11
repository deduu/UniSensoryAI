"""Chat application — first consumer of ``src.orchestration``.

Wires four agents (analyzer, direct-answerer, web-researcher, synthesizer)
into a hybrid routing pipeline:

- "direct"     → DirectAnswerer
- "search"     → WebResearcher → Synthesizer
- "ambiguous"  → DirectAnswerer with function-calling enabled (LLM may
                 invoke web_search itself)
"""
