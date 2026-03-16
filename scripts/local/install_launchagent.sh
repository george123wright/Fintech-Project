#!/bin/zsh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
AGENT_ID="com.quickbalance.local"
PLIST_PATH="$HOME/Library/LaunchAgents/$AGENT_ID.plist"
LOG_DIR="$HOME/Library/Logs"
START_SCRIPT="$REPO_DIR/scripts/local/start_single_process.sh"

mkdir -p "$HOME/Library/LaunchAgents" "$LOG_DIR"

cat > "$PLIST_PATH" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>$AGENT_ID</string>

  <key>ProgramArguments</key>
  <array>
    <string>$START_SCRIPT</string>
  </array>

  <key>RunAtLoad</key>
  <true/>

  <key>KeepAlive</key>
  <true/>

  <key>WorkingDirectory</key>
  <string>$REPO_DIR</string>

  <key>StandardOutPath</key>
  <string>$LOG_DIR/quickbalance.stdout.log</string>

  <key>StandardErrorPath</key>
  <string>$LOG_DIR/quickbalance.stderr.log</string>

  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key>
    <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
    <key>FRONTEND_DIST_DIR</key>
    <string>$REPO_DIR/dist</string>
  </dict>
</dict>
</plist>
PLIST

chmod 644 "$PLIST_PATH"

launchctl bootout "gui/$(id -u)/$AGENT_ID" >/dev/null 2>&1 || true
launchctl bootstrap "gui/$(id -u)" "$PLIST_PATH"
launchctl kickstart -k "gui/$(id -u)/$AGENT_ID"

echo "Installed and started $AGENT_ID"
echo "Frontend URL: http://127.0.0.1:8000"
echo "Logs:"
echo "  $LOG_DIR/quickbalance.stdout.log"
echo "  $LOG_DIR/quickbalance.stderr.log"
