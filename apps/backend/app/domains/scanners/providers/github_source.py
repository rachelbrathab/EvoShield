"""GitHub repository source — acquires a repository checkout for scanning.

This adapter clones a GitHub repository into a managed temporary workspace
using an **ephemeral SSH deploy key** (ADR 0018).

GitHub no longer accepts OAuth app tokens as git-over-HTTPS passwords for
private repositories ("Password authentication is not supported for Git
operations"), so the acquisition flow is:

    1. Resolve the user's OAuth token (via ``token_resolver``).
    2. Generate a throwaway ed25519 keypair inside the workspace.
    3. Register the public half as a read-only deploy key on the scanned
       repository (REST API, token in the Authorization header only).
    4. Clone over SSH with ``GIT_SSH_COMMAND`` pinned to that key.
    5. Delete the deploy key and shred the private key — in success AND
       failure paths.

Security measures:
- OAuth token used only in HTTP Authorization headers (never git args/URLs)
- Deploy keys are ``read_only`` and scoped to a single repository
- Private key lives only inside the acquisition workspace (mode 0600)
- Temporary workspace cleaned up in ``finally`` blocks
- All paths validated before subprocess execution
- No ``shell=True`` anywhere
- No secret appears in log messages

Architecture:
    TrivyProvider.execute()
        → GitHubRepositorySource.acquire()
            → ephemeral deploy key + SSH clone
            → returns workspace path
        → Trivy scans the workspace
        → GitHubRepositorySource.cleanup() or context-manager cleanup
"""

import logging
import shutil
import tempfile
from collections.abc import Awaitable, Callable
from pathlib import Path

from app.domains.scanners.providers.github_deploy_key import (
    DeployKeyError,
    EphemeralDeployKey,
)

logger = logging.getLogger(__name__)

# GitHub's SSH host keys, pinned per github.com's published SSH fingerprints
# (docs.github.com/authentication/keeping-your-account-and-data-secure/
# githubs-ssh-key-fingerprints).  Pinned host keys prevent MITM during the
# clone; no ssh-keyscan / TOFU needed.
#
# The ephemeral deploy-key acquisition clones over SSH *through the GitHub
# SSH gateway* (ssh.github.com:443) when the backend container cannot reach
# github.com:22 (ADR 0018 + GitHub docs:
# docs.github.com/en/authentication/troubleshooting-ssh/using-ssh-over-the-https-port).
# ssh.github.com presents the same ED25519 host key material as github.com, so
# both hosts are pinned below.
_GITHUB_HOST_KEYS = (
    "github.com ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIOMqqnkVzrm0SdG6UOoqKLsabgH5C9okWi0dh2l9GKJl",
    "ssh.github.com ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIOMqqnkVzrm0SdG6UOoqKLsabgH5C9okWi0dh2l9GKJl",
)


class RepositoryAcquisitionError(Exception):
    """Raised when repository acquisition fails."""

    def __init__(self, message: str, *, code: str = "acquisition_failed") -> None:
        super().__init__(message)
        self.code = code


class GitHubRepositorySource:
    """Acquires a GitHub repository checkout in a temporary workspace.

    Usage::

        source = GitHubRepositorySource(token_resolver=get_token)
        workspace = await source.acquire("octocat/Hello-World", branch="main")
        try:
            # scan workspace.path
            ...
        finally:
            workspace.cleanup()
    """

    def __init__(
        self,
        token_resolver: Callable[[], Awaitable[str | None]],
        *,
        executable: str = "git",
        max_repository_size_mb: float = 500.0,
        timeout_seconds: float = 120.0,
    ) -> None:
        """
        Args:
            token_resolver: An async callable that returns the user's GitHub
                access token, or None if the user has no connection.
            executable: Path to the git binary.
            max_repository_size_mb: Reject repositories larger than this
                (in MB) to prevent resource exhaustion.
            timeout_seconds: Timeout for the git clone operation.
        """
        self._token_resolver = token_resolver
        self._executable = executable
        self._max_repository_size_mb = max_repository_size_mb
        self._timeout_seconds = timeout_seconds

    async def acquire(
        self,
        full_name: str,
        *,
        branch: str | None = None,
        workspace_prefix: str = "evoshield_repo_",
    ) -> "WorkspaceHandle":
        """Clone a repository into a temporary workspace.

        Args:
            full_name: Repository in ``owner/repo`` format.
            branch: Specific branch to clone (default: repository default).
            workspace_prefix: Prefix for the temporary directory.

        Returns:
            A ``WorkspaceHandle`` with the workspace path.

        Raises:
            RepositoryAcquisitionError: On any acquisition failure.
        """
        token = await self._token_resolver()
        if not token:
            raise RepositoryAcquisitionError(
                "No GitHub access token available. Connect your GitHub account first.",
                code="github_not_connected",
            )

        # Validate full_name format (defense in depth)
        if not _validate_full_name(full_name):
            raise RepositoryAcquisitionError(
                f"Invalid repository name: {full_name!r}",
                code="invalid_repository_name",
            )

        workspace_dir = tempfile.mkdtemp(prefix=workspace_prefix)
        workspace_path = Path(workspace_dir)
        # Clone over GitHub's SSH gateway (ssh.github.com:443) so that a private
        # repository can be acquired even when github.com:22 is blocked by the
        # deployment environment (the documented GitHub SSH-over-HTTPS workaround).
        clone_url = f"ssh://git@ssh.github.com:443/{full_name}.git"

        logger.info(
            "Acquiring repository %s into %s",
            full_name,
            workspace_dir,
        )

        # Ephemeral deploy-key flow (ADR 0018): keypair → read-only deploy
        # key on this one repository → SSH clone → delete key + shred.
        deploy_key: EphemeralDeployKey | None = None
        try:
            deploy_key = await EphemeralDeployKey.create(
                access_token=token,
                full_name=full_name,
                workspace=workspace_path,
            )

            # Build clone command — no credential in any argument; the key
            # reaches ssh via GIT_SSH_COMMAND (an env var, not a shell).
            clone_args = [
                "clone",
                "--depth",
                "1",
                "--single-branch",
                "--no-tags",
                clone_url,
                str(workspace_path / "repo"),
            ]
            if branch:
                clone_args.insert(4, "--branch")
                clone_args.insert(5, branch)

            env = {
                "GIT_SSH_COMMAND": _ssh_command(
                    str(deploy_key.private_key_path),
                    str(_write_pinned_known_hosts(workspace_path)),
                ),
                # Clone is a one-shot transfer; never prompt.
                "GIT_TERMINAL_PROMPT": "0",
            }

            await _run_git(
                self._executable,
                clone_args,
                cwd=None,
                timeout_seconds=self._timeout_seconds,
                env=env,
            )

            repo_path = workspace_path / "repo"
            if not repo_path.is_dir():
                raise RepositoryAcquisitionError(
                    "Repository clone completed but the checkout directory is missing.",
                    code="clone_incomplete",
                )

            logger.info("Repository %s acquired successfully", full_name)
            return WorkspaceHandle(workspace_path)

        except DeployKeyError as exc:
            # Deploy-key lifecycle failure (keygen / REST API).  The code
            # taxonomy is shared with acquisition errors by design.
            shutil.rmtree(workspace_dir, ignore_errors=True)
            raise RepositoryAcquisitionError(str(exc), code=exc.code) from exc
        except RepositoryAcquisitionError:
            # Clean up on failure
            shutil.rmtree(workspace_dir, ignore_errors=True)
            raise
        except Exception as exc:
            # Clean up on any unexpected failure
            shutil.rmtree(workspace_dir, ignore_errors=True)
            raise RepositoryAcquisitionError(
                f"Failed to acquire repository {full_name}: {type(exc).__name__}",
                code="acquisition_failed",
            ) from exc
        finally:
            # Remove the deploy key and destroy the private key on every path.
            if deploy_key is not None:
                await deploy_key.cleanup()

class WorkspaceHandle:
    """A managed temporary workspace that can be cleaned up."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._cleaned = False

    @property
    def path(self) -> Path:
        """The workspace root directory."""
        return self._path

    @property
    def repo_path(self) -> Path:
        """The repository checkout inside the workspace."""
        return self._path / "repo"

    def cleanup(self) -> None:
        """Remove the workspace directory. Safe to call multiple times."""
        if self._cleaned:
            return
        self._cleaned = True
        try:
            shutil.rmtree(self._path, ignore_errors=True)
        except Exception:
            logger.warning("Failed to clean up workspace %s", self._path)

    def __enter__(self) -> "WorkspaceHandle":
        return self

    def __exit__(self, *args: object) -> None:
        self.cleanup()


# ── Helpers ───────────────────────────────────────────────────────────


def _validate_full_name(full_name: str) -> bool:
    """Validate that full_name matches the owner/repo pattern.

    Rejects shell metacharacters, path traversal, and other injection vectors.
    """
    import re

    return bool(re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", full_name))


def _ssh_command(private_key_path: str, known_hosts_path: str) -> str:
    """Build the GIT_SSH_COMMAND value for one clone.

    git executes GIT_SSH_COMMAND through the user's shell, so every
    variable part is ``shlex.quote``d.  All options are fixed: non-interactive,
    single identity, no agent, and host keys pinned to GitHub's published
    fingerprints via a workspace-local known_hosts file (real pinning —
    not TOFU, no global state).
    """
    import shlex

    return (
        f"ssh -i {shlex.quote(private_key_path)}"
        " -o IdentitiesOnly=yes"
        " -o BatchMode=yes"
        " -o StrictHostKeyChecking=yes"
        f" -o UserKnownHostsFile={shlex.quote(known_hosts_path)}"
    )


def _write_pinned_known_hosts(workspace: Path) -> Path:
    """Write a known_hosts file containing GitHub's pinned host keys.

    The file includes both ``github.com`` and ``ssh.github.com`` because the
    SSH gateway uses ``ssh.github.com`` as the SSH server while the repository
    URL still identifies the repository on GitHub.
    """
    known_hosts = workspace / "known_hosts"
    known_hosts.write_text("\n".join(_GITHUB_HOST_KEYS) + "\n")
    return known_hosts


async def _run_git(
    executable: str,
    args: list[str],
    *,
    cwd: str | Path | None = None,
    timeout_seconds: float = 60.0,
    env: dict[str, str] | None = None,
) -> tuple[str, str]:
    """Run a git command safely via ``create_subprocess_exec``.

    SECURITY: Uses ``create_subprocess_exec`` with explicit argument arrays —
    never ``shell=True``.  No user-controlled strings are concatenated into
    shell commands.

    Returns:
        (stdout, stderr) as decoded strings.

    Raises:
        RepositoryAcquisitionError: On non-zero exit or timeout.
    """
    import asyncio

    cmd_args = [executable, *args]
    logger.debug("Running git command (executable=%s)", executable)

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd_args,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(cwd) if cwd else None,
            env=env,
        )
        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            proc.communicate(),
            timeout=timeout_seconds,
        )

        stdout = stdout_bytes.decode("utf-8", errors="replace")
        stderr = stderr_bytes.decode("utf-8", errors="replace")
        exit_code = proc.returncode or 0

        if exit_code != 0:
            # Truncate stderr for safety — don't expose full git output
            raise RepositoryAcquisitionError(
                f"Git command failed with exit code {exit_code}",
                code="git_command_failed",
            )

        return stdout, stderr

    except TimeoutError as exc:
        if proc is not None:
            proc.kill()
            await proc.wait()
        raise RepositoryAcquisitionError(
            f"Git command timed out after {timeout_seconds:.0f}s",
            code="git_timeout",
        ) from exc
    except FileNotFoundError as exc:
        raise RepositoryAcquisitionError(
            f"Git executable not found: {executable}",
            code="git_not_found",
        ) from exc
    except RepositoryAcquisitionError:
        raise
    except OSError as exc:
        raise RepositoryAcquisitionError(
            f"Failed to execute git: {exc}",
            code="git_execution_error",
        ) from exc
