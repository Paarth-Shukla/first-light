#!/bin/bash
# Installs two launchd agents for the current macOS user:
#   com.firstlight.update  runs the pipeline every three hours (and once at login)
#   com.firstlight.serve   serves dist/ at http://localhost:8080
# Run:     scripts/install-local-schedule.sh
# Remove:  scripts/install-local-schedule.sh --uninstall
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
AGENTS="$HOME/Library/LaunchAgents"
PYTHON="$(command -v python3)"
LOGS="$ROOT/data/logs"
UID_NOW="$(id -u)"

unload() {
  for name in update serve; do
    launchctl bootout "gui/$UID_NOW/com.firstlight.$name" 2>/dev/null || true
    rm -f "$AGENTS/com.firstlight.$name.plist"
  done
}

if [[ "${1:-}" == "--uninstall" ]]; then
  unload
  echo "Removed the First Light launchd agents."
  exit 0
fi

mkdir -p "$AGENTS" "$LOGS"
unload

cat > "$AGENTS/com.firstlight.update.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.firstlight.update</string>
  <key>WorkingDirectory</key><string>$ROOT</string>
  <key>ProgramArguments</key><array><string>$PYTHON</string><string>-m</string><string>pipeline</string><string>all</string></array>
  <key>StartInterval</key><integer>10800</integer>
  <key>RunAtLoad</key><true/>
  <key>StandardOutPath</key><string>$LOGS/update.log</string>
  <key>StandardErrorPath</key><string>$LOGS/update.log</string>
</dict></plist>
PLIST

cat > "$AGENTS/com.firstlight.serve.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.firstlight.serve</string>
  <key>WorkingDirectory</key><string>$ROOT</string>
  <key>ProgramArguments</key><array><string>$PYTHON</string><string>scripts/serve.py</string></array>
  <key>KeepAlive</key><true/>
  <key>RunAtLoad</key><true/>
  <key>StandardOutPath</key><string>$LOGS/serve.log</string>
  <key>StandardErrorPath</key><string>$LOGS/serve.log</string>
</dict></plist>
PLIST

launchctl bootstrap "gui/$UID_NOW" "$AGENTS/com.firstlight.update.plist"
launchctl bootstrap "gui/$UID_NOW" "$AGENTS/com.firstlight.serve.plist"
echo "Installed. The paper is at http://localhost:8080 and updates every three hours."
echo "Logs: $LOGS"
