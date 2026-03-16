#!/bin/zsh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:${PATH:-}"
export FRONTEND_DIST_DIR="$REPO_DIR/dist"

cd "$REPO_DIR"
if [ ! -f "$REPO_DIR/dist/index.html" ]; then
  echo "[quick-balance] Frontend dist missing. Building..."
  npm run build
fi

PYTHON_BIN="$REPO_DIR/backend/.venv/bin/python"
if [ ! -x "$PYTHON_BIN" ]; then
  echo "[quick-balance] backend/.venv python not found, falling back to python3"
  PYTHON_BIN="$(command -v python3)"
fi

cd "$REPO_DIR/backend"
exec "$PYTHON_BIN" -m uvicorn app.main:app --host 127.0.0.1 --port 8000
