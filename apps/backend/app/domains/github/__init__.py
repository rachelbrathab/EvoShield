"""GitHub integration domain (Sprint 3+).

Owns GitHub OAuth, the GitHub API client, and repository metadata ingestion.

Dependency rule: this domain talks to the GitHub API via a thin client and
exposes normalized repository data to downstream domains (analysis, scanners)
through the API/worker layer — it never imports sibling domains.
"""
