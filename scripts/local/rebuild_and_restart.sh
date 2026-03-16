#!/bin/zsh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
AGENT_ID="com.quickbalance.local"

cd "$REPO_DIR"
npm run build
launchctl kickstart -k "gui/$(id -u)/$AGENT_ID"

echo "Rebuilt frontend and restarted $AGENT_ID"
