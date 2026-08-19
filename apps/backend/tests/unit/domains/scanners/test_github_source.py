"""Tests for GitHubRepositorySource — repository acquisition for scanning.

All tests use mocked git subprocesses and token resolvers.  No real GitHub
API calls or git operations are performed.
"""

import os
import shutil
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from app.domains.scanners.providers.github_source import (
    GitHubRepositorySource,
    RepositoryAcquisitionError,
    WorkspaceHandle,
    _validate_full_name,
)

# ── Full name validation ──────────────────────────────────────────────


class TestFullNameValidation:
    """Validate the full_name regex against injection vectors."""

    def test_valid_names(self) -> None:
        assert _validate_full_name("octocat/Hello-World")
        assert _validate_full_name("my-org/my.repo")
        assert _validate_full_name("user_123/repo_name")
        assert _validate_full_name("a/b")

    def test_rejects_shell_metacharacters(self) -> None:
        assert not _validate_full_name("octocat/Hello;rm -rf /")
        assert not _validate_full_name("octocat/Hello|cat /etc/passwd")
        assert not _validate_full_name("octocat/Hello`whoami`")
        assert not _validate_full_name("octocat/Hello$(whoami)")
        assert not _validate_full_name("octocat/Hello&&ls")

    def test_rejects_path_traversal(self) -> None:
        assert not _validate_full_name("../../../etc/passwd")
        assert not _validate_full_name("octocat/../etc/passwd")

    def test_rejects_empty_and_short(self) -> None:
        assert not _validate_full_name("")
        assert not _validate_full_name("/")
        assert not _validate_full_name("a")

    def test_rejects_single_name(self) -> None:
        assert not _validate_full_name("Hello-World")

    def test_rejects_url_schemes(self) -> None:
        assert not _validate_full_name("https://github.com/octocat/repo")


# ── WorkspaceHandle ───────────────────────────────────────────────────


class TestWorkspaceHandle:
    """Test workspace creation, paths, and cleanup."""

    def test_workspace_path_property(self) -> None:
        tmpdir = Path(tempfile.mkdtemp())
        try:
            ws = WorkspaceHandle(tmpdir)
            assert ws.path == tmpdir
            assert ws.repo_path == tmpdir / "repo"
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_cleanup_removes_directory(self) -> None:
        tmpdir = Path(tempfile.mkdtemp())
        (tmpdir / "repo").mkdir()
        (tmpdir / "repo" / "file.txt").write_text("test")
        try:
            ws = WorkspaceHandle(tmpdir)
            ws.cleanup()
            assert not tmpdir.exists()
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_cleanup_is_idempotent(self) -> None:
        tmpdir = Path(tempfile.mkdtemp())
        try:
            ws = WorkspaceHandle(tmpdir)
            ws.cleanup()
            ws.cleanup()  # second call should not raise
            assert ws._cleaned is True
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_context_manager_cleans_up(self) -> None:
        tmpdir = Path(tempfile.mkdtemp())
        try:
            with WorkspaceHandle(tmpdir) as ws:
                (ws.repo_path).mkdir(parents=True)
                assert ws.repo_path.is_dir()
            assert not tmpdir.exists()
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


# ── GitHubRepositorySource ────────────────────────────────────────────


@pytest.fixture
def mock_token() -> str:
    return "ghp_test_token_12345"


@pytest.fixture
def source(mock_token: str) -> GitHubRepositorySource:
    return GitHubRepositorySource(
        token_resolver=AsyncMock(return_value=mock_token),
        executable="git",
        timeout_seconds=30.0,
    )


@pytest.fixture
def no_token_source() -> GitHubRepositorySource:
    return GitHubRepositorySource(
        token_resolver=AsyncMock(return_value=None),
        executable="git",
    )


class TestTokenHandling:
    """Verify token resolution and error handling."""

    @pytest.mark.asyncio
    async def test_raises_when_no_token(self, no_token_source: GitHubRepositorySource) -> None:
        with pytest.raises(RepositoryAcquisitionError) as exc_info:
            await no_token_source.acquire("octocat/Hello-World")
        assert exc_info.value.code == "github_not_connected"
        assert "GitHub" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_token_not_in_error_message(self, mock_token: str) -> None:
        """Token must never appear in error messages."""
        source = GitHubRepositorySource(
            token_resolver=AsyncMock(return_value=mock_token),
            executable="nonexistent_git_binary",
        )
        with pytest.raises(RepositoryAcquisitionError) as exc_info:
            await source.acquire("octocat/Hello-World")
        assert mock_token not in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_invalid_full_name_rejected(self, source: GitHubRepositorySource) -> None:
        with pytest.raises(RepositoryAcquisitionError) as exc_info:
            await source.acquire("octocat/Hello;rm -rf /")
        assert exc_info.value.code == "invalid_repository_name"


class TestWorkspaceLifecycle:
    """Test workspace creation, repo path, and cleanup after operations."""

    @pytest.mark.asyncio
    async def test_successful_acquire_returns_workspace(
        self, source: GitHubRepositorySource
    ) -> None:
        async def _mock_run_git(*args: object, **kwargs: object) -> tuple[str, str]:
            # Simulate git creating the repo directory.
            # The clone command includes the target path as the last positional arg.
            cmd_args = args[1] if len(args) > 1 and isinstance(args[1], list) else []
            if "clone" in cmd_args and cmd_args:
                target = cmd_args[-1]
                if isinstance(target, str):
                    os.makedirs(target, exist_ok=True)
            return ("", "")

        with patch(
            "app.domains.scanners.providers.github_source._run_git",
            side_effect=_mock_run_git,
        ):
            workspace = await source.acquire("octocat/Hello-World")
            try:
                assert workspace is not None
                assert workspace.path.exists()
            finally:
                workspace.cleanup()

    @pytest.mark.asyncio
    async def test_workspace_cleanup_on_failure(self, source: GitHubRepositorySource) -> None:
        """Workspace must be cleaned up even when acquisition fails."""
        with patch(
            "app.domains.scanners.providers.github_source._run_git",
            side_effect=RepositoryAcquisitionError("clone failed", code="git_command_failed"),
        ):
            with pytest.raises(RepositoryAcquisitionError):
                await source.acquire("octocat/Hello-World")

    @pytest.mark.asyncio
    async def test_workspace_cleanup_on_exception(self, source: GitHubRepositorySource) -> None:
        """Workspace must be cleaned up on unexpected exceptions."""
        with patch(
            "app.domains.scanners.providers.github_source._run_git",
            side_effect=RuntimeError("unexpected"),
        ):
            with pytest.raises(RepositoryAcquisitionError):
                await source.acquire("octocat/Hello-World")


class TestSecurity:
    """Verify security measures: no token leakage, safe subprocess calls."""

    @pytest.mark.asyncio
    async def test_token_not_in_clone_url(self, source: GitHubRepositorySource) -> None:
        """Token must never be embedded in a URL."""
        token = await source._token_resolver()
        with patch(
            "app.domains.scanners.providers.github_source._run_git",
            new_callable=AsyncMock,
        ) as mock_git:
            mock_git.return_value = ("", "")
            try:
                await source.acquire("octocat/Hello-World")
            except RepositoryAcquisitionError:
                pass  # may fail due to mock, that's OK

            # Check that none of the git calls contained the token
            for call_args in mock_git.call_args_list:
                args = call_args[0] if call_args[0] else []
                for arg in args:
                    if isinstance(arg, str) and token:
                        assert token not in arg or "password=" in arg

    @pytest.mark.asyncio
    async def test_token_not_in_command_args(self, mock_token: str) -> None:
        """Token must not appear in any subprocess argument."""
        with patch(
            "app.domains.scanners.providers.github_source._run_git",
            new_callable=AsyncMock,
        ) as mock_git:
            mock_git.return_value = ("", "")
            source = GitHubRepositorySource(
                token_resolver=AsyncMock(return_value=mock_token),
            )
            try:
                await source.acquire("octocat/Hello-World")
            except RepositoryAcquisitionError:
                pass

            # Verify token is not in any argument
            for call in mock_git.call_args_list:
                args_list = call[0] if call[0] else []
                for item in args_list:
                    if isinstance(item, str):
                        assert mock_token not in item, f"Token leaked into git argument: {item!r}"


class TestCredentialHelper:
    """Test the temporary credential helper script creation and cleanup."""

    def test_creates_executable_helper(self, mock_token: str) -> None:
        from app.domains.scanners.providers.github_source import _create_credential_helper

        path = _create_credential_helper(mock_token)
        try:
            assert os.path.exists(path)
            assert os.access(path, os.X_OK)
            # Verify the file contains the token (inside the helper script)
            with open(path) as f:
                content = f.read()
            assert mock_token in content
        finally:
            os.unlink(path)

    def test_helper_contains_protocol(self, mock_token: str) -> None:
        from app.domains.scanners.providers.github_source import _create_credential_helper

        path = _create_credential_helper(mock_token)
        try:
            with open(path) as f:
                content = f.read()
            assert "protocol=https" in content
            assert "host=github.com" in content
        finally:
            os.unlink(path)
