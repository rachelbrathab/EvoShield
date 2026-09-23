"""Ephemeral SSH deploy keys for repository acquisition (ADR 0018).

Why deploy keys?
    GitHub no longer accepts OAuth app tokens as git-over-HTTPS credentials
    for private repositories ("Invalid username or token. Password
    authentication is not supported for Git operations.").  The GitHub
    documented alternative for OAuth-app integrations is a *repository
    deploy key*: EvoShield generates a throwaway ed25519 keypair per
    acquisition, registers the public half as a **read-only** deploy key on
    the scanned repository via the REST API, clones over SSH, then removes
    the deploy key and destroys the private half.

Security properties:
    - The OAuth token is used ONLY in the ``Authorization: Bearer`` header
      of the two API calls (create / delete deploy key).  It never reaches
      git, a command line, a URL, or a log.
    - The private key lives for the duration of one clone inside the
      acquisition workspace (mode 0600) and is shredded afterwards.
    - Deploy keys are created ``read_only=True`` and are scoped to exactly
      one repository — strictly narrower than the OAuth token's ``repo``
      scope.
    - All subprocesses (``ssh-keygen``) run via ``create_subprocess_exec``
      with explicit argument arrays — no shell.
    - Cleanup runs on success AND failure.  If the API delete itself fails,
      the key remains read-only and GitHub deletes OAuth-app deploy keys
      automatically when the user's OAuth token is revoked.
"""

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from pathlib import Path

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_API_VERSION = "2022-11-28"
_KEYGEN_TIMEOUT_SECONDS = 30.0


class DeployKeyError(Exception):
    """Raised when the ephemeral deploy-key lifecycle fails.

    ``code`` mirrors the repository-acquisition error taxonomy so
    ``GitHubRepositorySource`` can translate it 1:1.  Messages are
    user-facing and never contain the token, the key material, or URLs.
    """

    def __init__(self, message: str, *, code: str = "acquisition_failed") -> None:
        super().__init__(message)
        self.code = code


async def generate_keypair(
    directory: Path,
    *,
    comment: str,
    executable: str = "ssh-keygen",
) -> tuple[Path, str]:
    """Generate a fresh ed25519 keypair inside *directory*.

    Returns ``(private_key_path, public_key_body)``.  The private key is
    written by ssh-keygen with mode 0600 inside the acquisition workspace,
    so it never outlives the workspace.
    """
    key_path = directory / "id_ed25519"
    try:
        proc = await asyncio.create_subprocess_exec(
            executable,
            "-t",
            "ed25519",
            "-N",
            "",  # no passphrase — the key is ephemeral and 0600
            "-C",
            comment,
            "-f",
            str(key_path),
            "-q",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr_bytes = await asyncio.wait_for(
            proc.communicate(), timeout=_KEYGEN_TIMEOUT_SECONDS
        )
    except FileNotFoundError as exc:
        raise DeployKeyError(
            "SSH key generation is unavailable in this deployment.",
            code="ssh_keygen_unavailable",
        ) from exc
    except TimeoutError as exc:
        raise DeployKeyError("SSH key generation timed out.", code="keygen_failed") from exc

    if proc.returncode != 0:
        # ssh-keygen stderr never contains secret material at generation
        # time, but keep the message generic anyway.
        logger.debug("ssh-keygen failed: %s", stderr_bytes.decode(errors="replace"))
        raise DeployKeyError("Could not generate the temporary scan key.", code="keygen_failed")

    public_body = (directory / "id_ed25519.pub").read_text().strip()
    return key_path, public_body


async def _shred_file(path: Path) -> None:
    """Overwrite *path* with zeros, then unlink. Best effort, never raises."""
    import os

    def _shred_sync() -> None:
        try:
            size = path.stat().st_size
            with open(path, "r+b") as fh:
                fh.write(b"\x00" * size)
                fh.flush()
                os.fsync(fh.fileno())
        except OSError:
            pass
        try:
            path.unlink(missing_ok=True)
        except OSError:
            logger.warning("Failed to remove temporary key file %s", path)

    await asyncio.to_thread(_shred_sync)


class DeployKeyClient:
    """Minimal GitHub REST client for repository deploy keys.

    Mirrors ``GitHubAPIClient``'s conventions: token in the Authorization
    header only, typed error mapping, GitHub-specific detail isolated here.
    """

    def __init__(
        self,
        access_token: str,
        *,
        client: httpx.AsyncClient | None = None,
        base_url: str | None = None,
    ) -> None:
        self._base_url = (base_url or get_settings().github_api_url).rstrip("/")
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": _API_VERSION,
        }
        self._client = client or httpx.AsyncClient(
            timeout=15,
            headers=headers,
            base_url=self._base_url,
        )
        if client is not None:
            self._client.headers.update(headers)

    async def create(self, full_name: str, public_key: str, title: str) -> int:
        """Register a read-only deploy key; return the created key id."""
        payload = {
            "title": title,
            "key": public_key,
            "read_only": True,
        }
        try:
            response = await self._client.post(f"/repos/{full_name}/keys", json=payload)
        except httpx.HTTPError as exc:
            raise DeployKeyError(
                "GitHub is unreachable — could not register the temporary scan key.",
                code="github_api_unavailable",
            ) from exc
        if response.status_code == 201:
            key_id = response.json().get("id")
            if not isinstance(key_id, int):
                raise DeployKeyError(
                    "GitHub returned an invalid response while creating the scan key.",
                    code="github_api_unavailable",
                )
            return key_id
        raise self._error_for(response)

    async def delete(self, full_name: str, key_id: int) -> None:
        """Remove the deploy key. Raises on non-2xx responses."""
        try:
            response = await self._client.delete(f"/repos/{full_name}/keys/{key_id}")
        except httpx.HTTPError as exc:
            raise DeployKeyError(
                "GitHub is unreachable — could not remove the temporary scan key.",
                code="github_api_unavailable",
            ) from exc
        if response.status_code < 300:
            return
        raise self._error_for(response)

    @staticmethod
    def _error_for(response: httpx.Response) -> DeployKeyError:
        status = response.status_code
        if status == 401:
            return DeployKeyError(
                "Your GitHub connection is invalid or expired. Reconnect your account.",
                code="github_token_invalid",
            )
        if status == 403:
            # Covers both insufficient scope (write:public_key missing on the
            # stored OAuth authorization) and rate limiting — reconnecting
            # fixes the former, waiting the latter.
            return DeployKeyError(
                "GitHub refused to create the scan key. Reconnect your GitHub "
                "account to grant the required permission, then try again.",
                code="github_scope_insufficient",
            )
        if status == 404:
            return DeployKeyError(
                "This repository does not exist or is not accessible with the "
                "connected GitHub account.",
                code="acquisition_failed",
            )
        if status == 422:
            return DeployKeyError(
                "GitHub rejected the temporary scan key. Try the analysis again.",
                code="deploy_key_rejected",
            )
        if status >= 500:
            return DeployKeyError(
                "GitHub is having issues — try again shortly.",
                code="github_api_unavailable",
            )
        return DeployKeyError("GitHub refused the scan-key request.", code="acquisition_failed")


@dataclass
class EphemeralDeployKey:
    """One read-only deploy key bound to one acquisition."""

    _client: DeployKeyClient
    full_name: str
    private_key_path: Path
    key_id: int | None
    comment: str = field(default="", repr=False)

    @classmethod
    async def create(
        cls,
        *,
        access_token: str,
        full_name: str,
        workspace: Path,
        comment: str | None = None,
        keygen_executable: str = "ssh-keygen",
        api_base_url: str | None = None,
    ) -> "EphemeralDeployKey":
        """Generate a keypair and register it as a read-only deploy key.

        On API failure the freshly generated private key is destroyed
        before the error propagates.
        """
        title = comment or f"evoshield-scan-{uuid.uuid4().hex[:12]}"
        private_path, public_key = await generate_keypair(
            workspace, comment=title, executable=keygen_executable
        )
        client = DeployKeyClient(access_token, base_url=api_base_url)
        try:
            key_id = await client.create(full_name, public_key, title)
        except Exception:
            await _shred_file(private_path)
            raise
        logger.info("Created read-only deploy key for %s (key_id=%s)", full_name, key_id)
        return cls(
            _client=client,
            full_name=full_name,
            private_key_path=private_path,
            key_id=key_id,
            comment=title,
        )

    async def cleanup(self) -> None:
        """Delete the deploy key and shred the private key. Never raises."""
        if self.key_id is not None:
            try:
                await self._client.delete(self.full_name, self.key_id)
                logger.info("Removed deploy key for %s", self.full_name)
            except Exception as exc:
                # Read-only, single-repo, and auto-deleted when the user's
                # OAuth token is revoked — a leaked key is inert.
                logger.warning(
                    "Deploy key deletion failed (%s); GitHub removes "
                    "OAuth-app deploy keys when the token is revoked.",
                    type(exc).__name__,
                )
            self.key_id = None
        await _shred_file(self.private_key_path)
