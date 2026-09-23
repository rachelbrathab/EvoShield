# ADR 0018 — Repository acquisition via ephemeral SSH deploy keys

- **Status:** Accepted
- **Supersedes:** the git-over-HTTPS credential-helper acquisition path from ADR 0010
- **Related:** ADR 0007 (GitHub OAuth scopes), ADR 0009 (scanner architecture), ADR 0010 (repository acquisition)

## Context

Repository acquisition (`GitHubRepositorySource`) authenticated `git clone`
by passing the user's stored OAuth access token to git through a temporary
credential helper. Live testing against a private repository showed GitHub
rejecting every clone with:

```
remote: Invalid username or token. Password authentication is not supported
for Git operations.
fatal: Authentication failed for 'https://github.com/<owner>/<repo>.git/'
```

Investigation (verified inside the backend container with git 2.47.3):

1. **The credential-helper mechanism worked.** `git credential fill` with
   `GIT_CONFIG_COUNT`/`GIT_CONFIG_VALUE_0=!helper` correctly returned the
   token; the helper was invoked for clones of private repositories.
2. **GitHub rejected the credential itself.** GitHub App user tokens and
   classic PATs authenticate git-over-HTTPS, but the OAuth *app* token
   (`gho_…`) issued by EvoShield's login flow is no longer accepted as an
   HTTPS git password — regardless of the `repo` scope the user granted.
   This is a GitHub-side policy, not a bug in our plumbing.
3. Options considered:
   - **Personal access token configured as a server secret** — rejected:
     requires every user to hand EvoShield a long-lived PAT; shifts
     credential management onto users and out of the OAuth lifecycle.
   - **Embedding the token in the clone URL** — rejected: leaks into
     process listings, reflogs, and error output.
   - **GitHub App migration** — the better long-term design (fine-grained,
     short-lived installation tokens), but a full re-registration and
     re-authentication migration; documented below as future work.
   - **Repository deploy keys** — GitHub's documented mechanism for
     machine access to a single repository, creatable through the REST API
     with an OAuth token carrying `write:public_key`.

## Decision

Acquisition now provisions an **ephemeral, read-only SSH deploy key per
clone**:

```
acquire(full_name)
  ├─ token_resolver()                      → user's OAuth token (in-memory only)
  ├─ ssh-keygen ed25519 inside workspace   → private key never leaves workspace (0600)
  ├─ POST /repos/{owner}/{repo}/keys       → read-only deploy key (token in Authorization header)
  ├─ git clone git@github.com:{full_name}  → GIT_SSH_COMMAND pins host key; no shell
  └─ finally: DELETE /repos/.../keys/{id}  → deploy key removed
              + zero-fill + unlink         → private key shredded with workspace
```

Details:

- **New module** `app/domains/scanners/providers/github_deploy_key.py`
  owns key generation, the deploy-key REST calls (`DeployKeyClient`,
  mirroring `GitHubAPIClient` conventions), and the lifecycle wrapper
  (`EphemeralDeployKey`).  Scanner providers and the orchestrator are
  untouched — only `GitHubRepositorySource.acquire()` changed.
- **Scope change.** The OAuth scope becomes
  `read:user user:email repo write:public_key` (`write:public_key` is the
  documented requirement for OAuth-app deploy-key management). Existing
  authorizations lack it until the user reconnects; GitHub's 403 is mapped
  to a distinct `github_scope_insufficient` acquisition error whose message
  instructs reconnection. No other endpoint behaviour changes.
- **Least privilege.** Each deploy key is `read_only: true` and attached to
  exactly one repository for the duration of one clone — strictly narrower
  than the user's `repo`-scoped token, and far narrower than a server-wide
  PAT.
- **Host-key pinning.** GitHub's published ed25519 host key is written to a
  workspace-local `known_hosts`; `StrictHostKeyChecking=yes` rejects any
  mismatch. No TOFU, no global `known_hosts` mutation.
- **Cleanup on every path.** `EphemeralDeployKey.cleanup()` runs in the
  acquisition `finally` block: deploy key deleted (API), private key
  zero-filled and unlinked, then the whole workspace removed as before.
  If the API delete fails, the key remains read-only and single-repo;
  additionally, GitHub deletes OAuth-app deploy keys automatically when
  the user's OAuth token is revoked.
- **Image change.** `openssh-client` is added to the backend image
  (`ssh-keygen`, `ssh`). All invocations remain argument-array subprocesses.

## Alternatives explicitly not taken

- **GitHub App installation tokens** — architecturally superior
  (short-lived, per-installation) but requires a new app registration, new
  OAuth wiring, and user re-consent. Recorded as the preferred future
  migration if EvoShield outgrows the OAuth-app model.
- **Proxying git over the API tarball endpoint**
  (`GET /repos/{owner}/{repo}/tarball`) — no deploy key needed, but loses
  git history (Gitleaks scans only the working tree anyway, while Trivy and
  Semgrep are unaffected) and breaks `--depth 1` transfer efficiency for
  large repositories; also changes checkout semantics for future
  history-aware scanners. Rejected for now on behavioural fidelity.

## Consequences

- Private-repository scanning works again, without any user-side setup
  beyond the one-time OAuth (re-)authorization.
- Users who authorized before this change must click **Connect GitHub**
  once more; the UI's existing reconnect path (401 `github_token_invalid` /
  403 `github_scope_insufficient`) covers the flow.
- One extra GitHub API round-trip per acquisition (create + delete deploy
  key) — negligible against clone time.
- Deploy keys appear briefly in each scanned repository's **Settings →
  Deploy keys** as `evoshield-scan-…`; they are removed after cloning and
  are read-only while present.
- The `provider_tokens.scope` column now stores the widened scope string;
  it is informational (the stored token simply carries whatever GitHub
  granted).
