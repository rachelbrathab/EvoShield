#!/usr/bin/env bash
# EvoShield — run backend (uvicorn :8000) and frontend (next dev :3000)
# concurrently. Ctrl-C stops both.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

BACKEND_PID=""
FRONTEND_PID=""
STOPPED=0

cleanup() {
  if [ "$STOPPED" -eq 1 ]; then
    return
  fi
  STOPPED=1
  # Kill only the child PIDs we started — never the whole process group,
  # which would also take down the invoking terminal shell.
  [ -n "$BACKEND_PID" ] && kill "$BACKEND_PID" 2>/dev/null || true
  [ -n "$FRONTEND_PID" ] && kill "$FRONTEND_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo "▸ Backend  → http://localhost:8000/docs"
echo "▸ Frontend → http://localhost:3000"
echo "▸ Press Ctrl-C to stop both."

(cd apps/backend && exec uv run uvicorn app.main:app --reload --port 8000) &
BACKEND_PID=$!

(cd apps/frontend && exec npm run dev -- --port 3000) &
FRONTEND_PID=$!

wait "$BACKEND_PID" "$FRONTEND_PID"
