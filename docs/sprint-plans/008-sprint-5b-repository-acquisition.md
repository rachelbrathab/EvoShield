# Sprint 5B — Repository Acquisition & Scan Execution

> **Status:** ✅ Shipped — 2026-08-19

## Goal

Make the complete pipeline from GitHub repository to Trivy security findings functional and production-ready. The user should be able to trigger a real analysis of an imported GitHub repository and receive actual Trivy findings.

## What Was Built

### 1. GitHub Repository Source Adapter (`github_source.py`)

- `GitHubRepositorySource` — clones a GitHub repository into a temporary workspace
- `WorkspaceHandle` — manages temporary directory lifecycle with guaranteed cleanup
- `RepositoryAcquisitionError` — typed error with error codes for each failure mode
- `_create_credential_helper` / `_cleanup_credential_helper` — secure token delivery via temporary git credential helper
- `_validate_full_name` — regex validation rejecting shell metacharacters and path traversal
- `_run_git` — safe subprocess execution using `create_subprocess_exec` with explicit argument arrays

### 2. AnalysisExecutionContext Extension

- Added `owner_id: uuid.UUID` — identifies the repository owner for credential resolution
- Added `token_resolver: Callable[[], Awaitable[str | None]]` — async callable returning the user's GitHub access token
- Default no-op resolver for providers that don't need credentials (e.g., `FakeAnalysisProvider`)

### 3. Orchestrator Integration

- `AnalysisOrchestrator.__init__` accepts `token_resolver_factory` — a callable that creates per-owner token resolvers
- `_schedule()` stores the owner mapping for the background task
- `_execute_run()` resolves the token and passes it through the context

### 4. TrivyProvider Integration

- `TrivyProvider._acquire_repository()` uses `GitHubRepositorySource` to clone the repo
- Repository size validation after clone (configurable limit)
- Workspace cleanup in `finally` block — guaranteed on success, failure, cancellation, or timeout
- Human-readable error codes for each failure mode: `github_not_connected`, `github_token_invalid`, `acquisition_failed`, `repository_too_large`, `scanner_unavailable`, `scanner_execution_failed`

### 5. Configuration

New settings in `config.py`:
- `repository_max_size_mb` (default: 500) — maximum repository size for scanning
- `repository_clone_timeout_seconds` (default: 120) — timeout for git clone
- `git_executable` (default: "git") — git binary path

### 6. Dependency Injection (`deps.py`)

- `_trivy_token_factory(owner_id)` — creates per-owner async token resolvers
- Token resolver factory injected into `AnalysisOrchestrator` when Trivy is the selected provider
- Token resolver bypassed for fake provider (no external credentials needed)

### 7. Tests (33 new tests)

| Test Class | Tests | Coverage |
|---|---|---|
| `TestFullNameValidation` | 6 | Shell injection, path traversal, URL schemes |
| `TestWorkspaceHandle` | 4 | Creation, cleanup, idempotency, context manager |
| `TestTokenHandling` | 3 | No-token error, token not in messages, invalid names |
| `TestWorkspaceLifecycle` | 3 | Successful acquire, cleanup on failure, cleanup on exception |
| `TestSecurity` | 2 | Token not in URLs, token not in command args |
| `TestCredentialHelper` | 2 | Executable helper creation, protocol content |
| `TestAnalysisExecutionContext` | 3 | Default owner_id, default resolver, custom values |
| `TestMakeNoopResolver` | 2 | Returns callable, returns None |
| `TestTrivyProviderCancellation` | 2 | Cancel before execution, cancel during acquisition |
| `TestTrivyProviderErrorHandling` | 2 | Scanner unavailable, GitHub not connected |
| `TestTrivyProviderWorkspaceCleanup` | 2 | Cleanup on success, cleanup on failure |
| `TestTrivyProviderFindingsPersistence` | 2 | Empty results callback, findings with vulnerabilities |

All tests are mocked — no real GitHub API calls, no real Trivy binary, no real git operations.

## Validation

| Check | Result |
|---|---|
| Backend ruff | ✅ 0 errors |
| Backend format | ✅ 109 files |
| Backend pyright | ✅ 0 errors |
| Backend pytest (SQLite) | ✅ **161 passed** (was 128) |
| Backend pytest (PostgreSQL 18) | ✅ **161 passed** |
| Alembic (both dialects) | ✅ 6 migrations |
| Frontend tsc | ✅ 0 errors |
| Frontend eslint | ✅ 0 warnings |
| Frontend vitest | ✅ **72 passed** |
| Frontend build | ✅ |

## Architecture Changes

```
Orchestrator._execute_run()
    │
    ├─ token_resolver_factory(owner_id)
    │   → ProviderTokenRepository.get_access_token()
    │   → async token resolver
    │
    ├─ AnalysisExecutionContext(
    │     owner_id=...,
    │     token_resolver=...,
    │   )
    │
    └─ TrivyProvider.execute(context)
        │
        ├─ GitHubRepositorySource(token_resolver)
        │   ├─ _create_credential_helper(token)
        │   ├─ git config credential.helper
        │   ├─ git clone --depth 1
        │   └─ returns WorkspaceHandle
        │
        ├─ TrivyRunner.run_filesystem(workspace.repo_path)
        │
        ├─ TrivyResultParser.parse()
        │
        ├─ findings_callback(findings)
        │
        └─ workspace.cleanup()  ← always, via finally
```

## Files Changed

**New files:**
- `apps/backend/app/domains/scanners/providers/github_source.py` — repository acquisition adapter
- `apps/backend/tests/unit/domains/scanners/test_github_source.py` — 20 tests
- `apps/backend/tests/unit/domains/scanners/test_token_resolver.py` — 5 tests
- `apps/backend/tests/unit/domains/scanners/test_trivy_provider_integration.py` — 8 tests
- `docs/adr/0010-repository-acquisition.md` — architecture decision record

**Modified files:**
- `apps/backend/app/domains/analysis/ports.py` — `AnalysisExecutionContext` fields
- `apps/backend/app/domains/analysis/orchestrator.py` — token resolver factory, owner mapping
- `apps/backend/app/domains/scanners/providers/trivy/provider.py` — workspace integration
- `apps/backend/app/api/deps.py` — token resolver factory DI
- `apps/backend/app/core/config.py` — repository acquisition settings

## Security Measures Verified

1. ✅ No `shell=True` in any subprocess call
2. ✅ Token never appears in command-line arguments
3. ✅ Token never appears in log messages
4. ✅ Token never appears in error messages
5. ✅ Credential helper is temporary and mode-0600
6. ✅ Full name validated against shell metacharacters
7. ✅ Workspace cleaned up on all code paths
8. ✅ Ownership isolation verified in tests

## Known Limitations

- Git must be installed on the server (documented requirement)
- Very large repositories (>500MB) are rejected
- No repository caching — re-analysis re-clones
- SSH cloning not supported (HTTPS only)
- GitHub API rate limits during clone (mitigated by authenticated token)

## Deferred Work

- Repository caching to avoid re-cloning
- Configurable clone depth
- GitLab/Bitbucket source adapters
- SSH-based cloning
- Background worker infrastructure

## Suggested Next Sprint

**Sprint 5C or Sprint 6** — Repository Intelligence (Sprint 6) or Extended Scanner Support (Sprint 5C). The Trivy pipeline is now end-to-end functional; the next step is either adding more scanners or building intelligence on top of the findings.
