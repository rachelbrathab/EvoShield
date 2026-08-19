"""ScannerWorkspace unit tests.

Tests the temporary workspace manager for scanner execution.
"""

import pytest

from app.domains.scanners.workspace import ScannerWorkspace


@pytest.mark.asyncio
async def test_workspace_creates_temp_directory() -> None:
    async with ScannerWorkspace() as ws:
        assert ws.path.exists()
        assert ws.path.is_dir()


@pytest.mark.asyncio
async def test_workspace_cleans_up_on_exit() -> None:
    path = None
    async with ScannerWorkspace() as ws:
        path = ws.path
        assert path.exists()
    assert not path.exists()


@pytest.mark.asyncio
async def test_workspace_cleanup_is_idempotent() -> None:
    async with ScannerWorkspace() as ws:
        ws.cleanup()
        ws.cleanup()  # should not raise


@pytest.mark.asyncio
async def test_workspace_path_raises_before_enter() -> None:
    ws = ScannerWorkspace()
    with pytest.raises(RuntimeError, match="not entered"):
        _ = ws.path


@pytest.mark.asyncio
async def test_workspace_path_returns_path_object() -> None:
    from pathlib import Path

    async with ScannerWorkspace(prefix="test_") as ws:
        assert isinstance(ws.path, Path)
        assert "test_" in ws.path.name
