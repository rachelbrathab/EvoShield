"""AI security assistant domain (Sprint 10+).

Owns the conversational interface over findings, predictions and
recommendations (LLM orchestration, prompt/context assembly, grounding).

Dependency rule: consumes domain data via the orchestration layer; never
imports sibling domains.
"""
