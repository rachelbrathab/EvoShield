# ADR 0010 — Repository Acquisition & Scan Execution Pipeline

- **Status:** Accepted
- **Date:** 2026-08-19
- **Deciders:** Tech lead (Buffy), project owner
- **Technical story:** Sprint 5B — making the Trivy pipeline end-to-end functional

## Context

Sprint 5A built the scanner infrastructure (orchestrator, provider port, Trivy adapter, findings model) but left one critical gap: `TrivyProvider._get_scan_path()` returned `None`. The entire pipeline was wired except for getting the repository source into a temporary workspace for scanning.

The challenge: Trivy needs a filesystem checkout, but EvoShield stores repository metadata (not source code). The user's GitHub access token must authenticate the clone, but it must never be logged, passed as a command-line argument, or written to disk.

## Decision

### 1. GitHub Repository Source Adapter

Introduce `GitHubRepositorySource` — a provider that clones a GitHub repository into a managed temporary workspace using the user's stored access token.

- **Location:** `app/domains/scanners/providers/github_source.py`
- **Token delivery:** A `Callable[[], Awaitable[str | None]]` (async token resolver) is passed through the `AnalysisExecutionContext`
- **Authentication:** Git credential helper script (temporary, deleted after clone) — token never in URLs or command-line arguments
- **Cleanup:** `WorkspaceHandle` context manager guarantees directory removal on success, failure, or cancellation

### 2. AnalysisExecutionContext Extension

Add two new fields:

- `owner_id: uuid.UUID` — identifies the user for credential resolution
- `token_resolver: Callable[[], Awaitable[str | None]]` — async callable returning the user's GitHub token

These are set by the orchestrator at dispatch time using a `token_resolver_factory` injected via DI.

### 3. Token Resolution Chain

```
deps.py → token_resolver_factory(owner_id) → async def _resolve()
    → ProviderTokenRepository.get_access_token(owner_id, "github")
    → passed into AnalysisExecutionContext
    → GitHubRepositorySource.acquire() awaits it
    → token used in credential helper, never in subprocess args
```

### 4. Resource Limits

Configurable via environment:

- `REPOSITORY_MAX_SIZE_MB` (default: 500) — reject oversized repos
- `REPOSITORY_CLONE_TIMEOUT_SECONDS` (default: 120)
- `GIT_EXECUTABLE` (default: "git")

Exceeded limits produce clear application-level error codes.

## Security Considerations

1. **No token in URLs:** Clone uses `https://github.com/owner/repo.git` — no embedded credentials
2. **No token in command-line arguments:** Token passed via a temporary credential helper script
3. **Credential helper is temporary:** Created with mode `0o600`, deleted after clone
4. **Token never logged:** Provider logs repository names, never tokens
5. **Safe subprocess:** `create_subprocess_exec` with explicit argument arrays — never `shell=True`
6. **Path validation:** `full_name` regex-validated against shell metacharacters and path traversal
7. **Workspace isolation:** Unique temp directory per analysis, cleaned up on all code paths

## Consequences

### Positive
- Complete end-to-end pipeline: GitHub repo → workspace → Trivy → findings
- Token never exposed through logs, subprocess args, or API responses
- Future scanners (Syft, Grype, Semgrep, Gitleaks) can reuse `GitHubRepositorySource`
- Workspace cleanup is guaranteed via `finally` blocks
- Resource limits prevent abuse

### Negative
- Adds ~200 lines of acquisition code
- Credential helper is a shell script (acceptable — it's temporary and mode-0600)
- Token lookup happens in the background task (async, via session factory)

### Risks
- Git must be installed on the server (documented requirement)
- Very large repositories (>500MB) are rejected — configurable
- GitHub API rate limits during clone (token already authenticated, minimal risk)

## Future Work
- Repository caching to avoid re-cloning for re-analysis
- Shallow clone depth configuration
- GitLab/Bitbucket source adapters
- SSH-based cloning for self-hosted instances
