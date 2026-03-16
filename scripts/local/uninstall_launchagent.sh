#!/bin/zsh
set -euo pipefail

AGENT_ID="com.quickbalance.local"
PLIST_PATH="$HOME/Library/LaunchAgents/$AGENT_ID.plist"

launchctl bootout "gui/$(id -u)/$AGENT_ID" >/dev/null 2>&1 || true
rm -f "$PLIST_PATH"

echo "Uninstalled $AGENT_ID"
