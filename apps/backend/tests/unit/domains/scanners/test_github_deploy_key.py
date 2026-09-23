"""Tests for the ephemeral deploy-key lifecycle (ADR 0018).

All GitHub API calls are mocked; ``ssh-keygen`` runs against a real
temporary directory (it is a local binary, no network involved).  No real
GitHub credentials or network calls are used.
"""

import shutil
import stat
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.domains.scanners.providers.github_deploy_key import (
    DeployKeyClient,
    DeployKeyError,
    EphemeralDeployKey,
    generate_keypair,
)

# ── Keypair generation ────────────────────────────────────────────────


class TestKeypairGeneration:
    def test_generates_keypair_in_workspace(self) -> None:
        tmpdir = Path(tempfile.mkdtemp())
        try:
            private, public = _run(generate_keypair(tmpdir, comment="test@evoshield"))
            assert private.exists()
            assert public.startswith("ssh-ed25519 ")
            assert "test@evoshield" in public
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_private_key_mode_is_0600(self) -> None:
        tmpdir = Path(tempfile.mkdtemp())
        try:
            private, _ = _run(generate_keypair(tmpdir, comment="c"))
            mode = stat.S_IMODE(private.stat().st_mode)
            assert mode == 0o600
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_missing_binary_raises(self) -> None:
        tmpdir = Path(tempfile.mkdtemp())
        try:
            with pytest.raises(DeployKeyError) as exc_info:
                _run(generate_keypair(tmpdir, comment="c", executable="nonexistent-ssh-keygen"))
            assert exc_info.value.code == "ssh_keygen_unavailable"
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


def _run(awaitable):  # type: ignore[no-untyped-def]
    """Bridge a coroutine into a fresh event loop (sync tests only)."""
    import asyncio

    return asyncio.run(awaitable)


# ── DeployKeyClient error mapping ─────────────────────────────────────


def _response(status_code: int) -> httpx.Response:
    request = httpx.Request("POST", "https://api.github.com/repos/o/r/keys")
    return httpx.Response(status_code, request=request, json={"message": "x"})


class TestDeployKeyClientErrors:
    @pytest.mark.asyncio
    async def test_default_client_uses_github_base_url_and_auth_headers(self) -> None:
        client = DeployKeyClient("gho_test_token")
        try:
            assert str(client._client.base_url) == "https://api.github.com"
            assert client._client.headers["Authorization"] == "Bearer gho_test_token"
            assert client._client.headers["Accept"] == "application/vnd.github+json"
            assert client._client.headers["X-GitHub-Api-Version"] == "2022-11-28"
        finally:
            await client._client.aclose()

    @pytest.mark.asyncio
    async def test_create_resolves_repository_deploy_key_url(self) -> None:
        requests: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return httpx.Response(201, request=request, json={"id": 42})

        transport_client = httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            base_url="https://api.github.com",
        )
        client = DeployKeyClient("token", client=transport_client)
        try:
            assert await client.create("octocat/Hello-World", "ssh-ed25519 AAA", "title") == 42
            assert requests[0].method == "POST"
            assert str(requests[0].url) == "https://api.github.com/repos/octocat/Hello-World/keys"
        finally:
            await transport_client.aclose()

    @pytest.mark.asyncio
    async def test_delete_resolves_repository_deploy_key_url(self) -> None:
        requests: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return httpx.Response(204, request=request)

        transport_client = httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            base_url="https://api.github.com",
        )
        client = DeployKeyClient("token", client=transport_client)
        try:
            await client.delete("octocat/Hello-World", 42)
            assert requests[0].method == "DELETE"
            assert str(requests[0].url) == "https://api.github.com/repos/octocat/Hello-World/keys/42"
        finally:
            await transport_client.aclose()

    @pytest.mark.asyncio
    async def test_401_maps_to_token_invalid(self) -> None:
        client = DeployKeyClient("token")
        with patch.object(
            client._client, "post", new_callable=AsyncMock, return_value=_response(401)
        ):
            with pytest.raises(DeployKeyError) as exc_info:
                await client.create("o/r", "ssh-ed25519 AAA", "title")
        assert exc_info.value.code == "github_token_invalid"

    @pytest.mark.asyncio
    async def test_403_maps_to_scope_insufficient(self) -> None:
        client = DeployKeyClient("token")
        with patch.object(
            client._client, "post", new_callable=AsyncMock, return_value=_response(403)
        ):
            with pytest.raises(DeployKeyError) as exc_info:
                await client.create("o/r", "ssh-ed25519 AAA", "title")
        assert exc_info.value.code == "github_scope_insufficient"

    @pytest.mark.asyncio
    async def test_201_returns_key_id(self) -> None:
        client = DeployKeyClient("token")
        response = httpx.Response(
            201, request=httpx.Request("POST", "https://api.github.com/x"), json={"id": 42}
        )
        with patch.object(client._client, "post", new_callable=AsyncMock, return_value=response):
            key_id = await client.create("o/r", "ssh-ed25519 AAA", "title")
        assert key_id == 42

    @pytest.mark.asyncio
    async def test_create_sends_read_only_true(self) -> None:
        client = DeployKeyClient("token")
        response = httpx.Response(
            201, request=httpx.Request("POST", "https://api.github.com/x"), json={"id": 1}
        )
        with patch.object(
            client._client, "post", new_callable=AsyncMock, return_value=response
        ) as mock_post:
            await client.create("o/r", "ssh-ed25519 AAA", "title")
        payload = mock_post.call_args.kwargs["json"]
        assert payload["read_only"] is True
        assert payload["key"] == "ssh-ed25519 AAA"

    @pytest.mark.asyncio
    async def test_token_never_in_error_messages(self) -> None:
        client = DeployKeyClient("gho_super_secret_token_value")
        for status in (401, 403, 404, 422, 500):
            with patch.object(
                client._client, "post", new_callable=AsyncMock, return_value=_response(status)
            ):
                with pytest.raises(DeployKeyError) as exc_info:
                    await client.create("o/r", "ssh-ed25519 AAA", "title")
            assert "gho_super_secret_token_value" not in str(exc_info.value)


# ── EphemeralDeployKey lifecycle ──────────────────────────────────────


class TestEphemeralDeployKeyLifecycle:
    @pytest.mark.asyncio
    async def test_create_shreds_private_key_on_api_failure(self) -> None:
        tmpdir = Path(tempfile.mkdtemp())
        try:
            with (
                patch(
                    "app.domains.scanners.providers.github_deploy_key.DeployKeyClient.create",
                    new_callable=AsyncMock,
                    side_effect=DeployKeyError("refused", code="github_scope_insufficient"),
                ),
                patch(
                    "app.domains.scanners.providers.github_deploy_key.DeployKeyClient.__init__",
                    return_value=None,
                ),
            ):
                with pytest.raises(DeployKeyError):
                    await EphemeralDeployKey.create(
                        access_token="token",
                        full_name="o/r",
                        workspace=tmpdir,
                    )
            # The private key must NOT survive the failed registration.
            assert not (tmpdir / "id_ed25519").exists()
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    @pytest.mark.asyncio
    async def test_cleanup_deletes_key_and_shreds_private(self) -> None:
        tmpdir = Path(tempfile.mkdtemp())
        try:
            private, _ = await generate_keypair(tmpdir, comment="c")
            assert private.exists()

            client = MagicMock(spec=DeployKeyClient)
            client.delete = AsyncMock()
            key = EphemeralDeployKey(
                _client=client,
                full_name="o/r",
                private_key_path=private,
                key_id=7,
            )
            await key.cleanup()
            client.delete.assert_awaited_once_with("o/r", 7)
            assert not private.exists()
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    @pytest.mark.asyncio
    async def test_cleanup_succeeds_even_when_api_delete_fails(self) -> None:
        tmpdir = Path(tempfile.mkdtemp())
        try:
            private, _ = await generate_keypair(tmpdir, comment="c")
            client = MagicMock(spec=DeployKeyClient)
            client.delete = AsyncMock(side_effect=DeployKeyError("boom"))
            key = EphemeralDeployKey(
                _client=client,
                full_name="o/r",
                private_key_path=private,
                key_id=7,
            )
            # Never raises.
            await key.cleanup()
            assert not private.exists()
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    @pytest.mark.asyncio
    async def test_cleanup_without_key_id_still_shreds(self) -> None:
        tmpdir = Path(tempfile.mkdtemp())
        try:
            private, _ = await generate_keypair(tmpdir, comment="c")
            client = MagicMock(spec=DeployKeyClient)
            client.delete = AsyncMock()
            key = EphemeralDeployKey(
                _client=client,
                full_name="o/r",
                private_key_path=private,
                key_id=None,
            )
            await key.cleanup()
            client.delete.assert_not_awaited()
            assert not private.exists()
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)
