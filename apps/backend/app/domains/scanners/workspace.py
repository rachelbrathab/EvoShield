"""Temporary workspace manager for scanner execution.

Scanners operate on a controlled temporary directory that is:
1. Created before the scan
2. Cleaned up after the scan (success or failure)
3. Never exposed through the API

The workspace is a `tempfile.TemporaryDirectory` used as a context manager
to guarantee cleanup.  Scanner adapters receive the workspace path and are
responsible for writing output there (e.g., Trivy JSON results).
"""

import shutil
import tempfile
from pathlib import Path


class ScannerWorkspace:
    """A managed temporary directory for scanner execution.

    Usage::

        async with ScannerWorkspace(prefix="trivy_") as ws:
            # ws.path is the temporary directory
            # Scanner writes output to ws.path
            pass
        # Directory is automatically cleaned up
    """

    def __init__(self, *, prefix: str = "evoshield_scan_") -> None:
        self._prefix = prefix
        self._tmpdir: tempfile.TemporaryDirectory[str] | None = None
        self._path: Path | None = None

    async def __aenter__(self) -> "ScannerWorkspace":
        self._tmpdir = tempfile.TemporaryDirectory(prefix=self._prefix)
        self._path = Path(self._tmpdir.name)
        return self

    async def __aexit__(self, *args: object) -> None:
        self.cleanup()

    @property
    def path(self) -> Path:
        """The temporary directory path."""
        if self._path is None:
            raise RuntimeError("Workspace not entered — use 'async with'")
        return self._path

    def cleanup(self) -> None:
        """Force cleanup of the temporary directory.

        Safe to call multiple times.  Called automatically by __aexit__
        but can also be called explicitly if the context manager is not used.
        """
        if self._tmpdir is not None:
            try:
                shutil.rmtree(self._tmpdir.name, ignore_errors=True)
            finally:
                self._tmpdir = None
                self._path = None
