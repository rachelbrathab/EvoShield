#!/usr/bin/env bash
# EvoShield — one-command setup: frontend deps + backend env + migrations.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "▸ Installing frontend dependencies…"
npm --prefix apps/frontend install

echo "▸ Syncing backend environment (uv)…"
if ! command -v uv >/dev/null 2>&1; then
  echo "✗ 'uv' not found. Install it: https://docs.astral.sh/uv/  (brew install uv)" >&2
  exit 1
fi
(cd apps/backend && uv sync)

echo "▸ Applying database migrations…"
(cd apps/backend && uv run alembic upgrade head)

echo
echo "✓ Setup complete."
echo "  Run 'npm run dev' to start frontend (:3000) and backend (:8000)."
