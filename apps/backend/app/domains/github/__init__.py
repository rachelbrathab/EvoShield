"""GitHub/source-provider domain — repository integration (Sprint 3A).

Owns repository ingestion for *any* source provider behind a port
(`ports.py`): the `GitHubAPIClient` adapter isolates all GitHub-specific
code, `RepositoryService` holds the business rules (idempotent import,
sync, deletion, scoped queries), and `RepositoryRepository` is the data
access for the `repositories` aggregate. GitLab/Bitbucket/Azure DevOps are
future adapters implementing the same `GitHubRepoProvider` port — no
downstream changes required (docs/module-dependency.md).
"""
