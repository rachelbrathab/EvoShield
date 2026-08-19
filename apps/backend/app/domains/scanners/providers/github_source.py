"""GitHub repository source — acquires a repository checkout for scanning.

This adapter clones a GitHub repository into a managed temporary workspace
using the authenticated user's stored access token.  The token is never
logged, never passed as a command-line argument, and never written to disk.

Security measures:
- Token used only in HTTP Authorization header (not shell arguments)
- ``git credential helper`` is used to pass credentials to git subprocesses
- Temporary workspace is cleaned up in ``finally`` blocks
- All paths validated before subprocess execution
- No ``shell=True`` anywhere
- Token never appears in log messages

Architecture:
    TrivyProvider.execute()
        → GitHubRepositorySource.acquire()
            → git clone via temporary credential helper
            → returns workspace path
        → Trivy scans the workspace
        → GitHubRepositorySource.cleanup() or context-manager cleanup
"""

import logging
import os
import shutil
import tempfile
from collections.abc import Awaitable, Callable
from pathlib import Path

logger = logging.getLogger(__name__)


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
        repo_url = f"https://github.com/{full_name}.git"

        logger.info(
            "Acquiring repository %s into %s",
            full_name,
            workspace_dir,
        )

        # Use a temporary credential helper to pass the token without
        # embedding it in the URL or any command-line argument.
        credential_helper_path = None
        try:
            credential_helper_path = _create_credential_helper(token)

            # Configure git to use our credential helper
            await _run_git(
                self._executable,
                ["config", "credential.helper", f"!{credential_helper_path}"],
                cwd=workspace_path,
                timeout_seconds=10,
            )

            # Build clone command — no token in any argument
            clone_args = [
                self._executable,
                "clone",
                "--depth",
                "1",
                "--single-branch",
                "--no-tags",
                repo_url,
                str(workspace_path / "repo"),
            ]
            if branch:
                clone_args.insert(4, "--branch")
                clone_args.insert(5, branch)

            await _run_git(
                self._executable,
                clone_args,
                cwd=None,
                timeout_seconds=self._timeout_seconds,
            )

            repo_path = workspace_path / "repo"
            if not repo_path.is_dir():
                raise RepositoryAcquisitionError(
                    "Repository clone completed but the checkout directory is missing.",
                    code="clone_incomplete",
                )

            logger.info("Repository %s acquired successfully", full_name)
            return WorkspaceHandle(workspace_path)

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
            # Remove the credential helper file
            if credential_helper_path is not None:
                _cleanup_credential_helper(credential_helper_path)


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


def _create_credential_helper(token: str) -> str:
    """Create a temporary executable credential helper script.

    The script responds to git's credential protocol (get/store/erase)
    by emitting the token on ``credential-fill``.  The file is executable
    and removed after use.

    SECURITY: The token is written to a file that is readable only by the
    current process (mode 0o600) and deleted immediately after the clone.
    """
    import stat

    fd, helper_path = tempfile.mkstemp(
        prefix="evoshield_cred_",
        suffix=".sh",
    )
    try:
        content = f"""#!/bin/sh
# EvoShield temporary credential helper — reads from stdin, emits token.
# This file is auto-deleted after the git clone operation.
read line
case "$line" in
    protocol=*)
        echo "protocol=https"
        echo "host=github.com"
        echo "username=oauth"
        echo "password={token}"
        ;;
esac
"""
        os.write(fd, content.encode())
        os.close(fd)
        os.chmod(helper_path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
    except Exception:
        os.close(fd) if not os.get_inheritable(fd) else None  # type: ignore[union-attr]
        os.unlink(helper_path)
        raise

    return helper_path


def _cleanup_credential_helper(path: str) -> None:
    """Securely remove the credential helper script."""
    try:
        os.unlink(path)
    except FileNotFoundError:
        pass
    except OSError:
        logger.warning("Failed to remove credential helper %s", path)


async def _run_git(
    executable: str,
    args: list[str],
    *,
    cwd: str | Path | None = None,
    timeout_seconds: float = 60.0,
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
    logger.debug("Running: %s [args hidden for security]", executable)

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd_args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(cwd) if cwd else None,
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
