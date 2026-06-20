#!/bin/bash
# setup_daily_refresh.sh — Install/refresh the LaunchAgent that runs run_mvp.sh daily at 06:00.
#
# Reconstructed 2026-05-21 after worktree-collision wipe lost the previous version.
# The plist (~/Library/LaunchAgents/com.footballdb.daily-refresh.plist) was preserved
# during the disaster — this script is idempotent: writes it fresh + reloads launchctl.
#
# Usage:
#   bash setup_daily_refresh.sh           # install + load
#   bash setup_daily_refresh.sh --uninstall  # unload + remove
#   bash setup_daily_refresh.sh --verify  # status only
#
# Verify after install:
#   launchctl list | grep footballdb
#
set -euo pipefail

BASE="/Users/cmk/Documents/CMK Digital/Football Coaches DB"
LABEL="com.footballdb.daily-refresh"
PLIST="$HOME/Library/LaunchAgents/${LABEL}.plist"

# --- handle modes ---
case "${1:-install}" in
  --uninstall)
    echo "Unloading $LABEL..."
    launchctl unload "$PLIST" 2>/dev/null || true
    rm -f "$PLIST"
    echo "✓ Removed."
    exit 0
    ;;
  --verify)
    echo "=== launchctl list ==="
    launchctl list | grep footballdb || echo "  (not loaded)"
    echo ""
    echo "=== plist on disk ==="
    ls -la "$PLIST" 2>/dev/null || echo "  (missing)"
    echo ""
    echo "=== run_mvp.sh on disk ==="
    ls -la "$BASE/run_mvp.sh" 2>/dev/null || echo "  (missing — daily refresh would fail!)"
    exit 0
    ;;
esac

# --- pre-flight: run_mvp.sh must exist ---
if [ ! -f "$BASE/run_mvp.sh" ]; then
  echo "✗ Aborting: $BASE/run_mvp.sh is missing. Reconstruct it first." >&2
  exit 1
fi

# --- write plist (idempotent overwrite) ---
mkdir -p "$HOME/Library/LaunchAgents"
cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>${LABEL}</string>

    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>-lc</string>
        <string>cd "${BASE}" &amp;&amp; bash run_mvp.sh &gt;&gt; tmp/daily-refresh.log 2&gt;&amp;1 &amp;&amp; curl -s -H "Title: Coach-DB Daily Refresh" -H "Priority: default" -d "OK — networks + dashboards deployed (\`date '+%H:%M'\`)" https://ntfy.sh/cmk-coachdb || curl -s -H "Title: Coach-DB Daily Refresh FAILED" -H "Priority: high" -d "Pipeline error at \`date '+%H:%M'\` — check tmp/daily-refresh.log" https://ntfy.sh/cmk-coachdb</string>
    </array>

    <key>WorkingDirectory</key>
    <string>${BASE}</string>

    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>6</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>

    <key>RunAtLoad</key>
    <false/>

    <key>StandardOutPath</key>
    <string>${BASE}/tmp/daily-refresh.stdout.log</string>

    <key>StandardErrorPath</key>
    <string>${BASE}/tmp/daily-refresh.stderr.log</string>

    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
        <key>HOME</key>
        <string>${HOME}</string>
    </dict>

    <key>ProcessType</key>
    <string>Background</string>
</dict>
</plist>
EOF
echo "✓ Wrote $PLIST"

# --- reload via launchctl ---
launchctl unload "$PLIST" 2>/dev/null || true
launchctl load "$PLIST"
echo "✓ Loaded into launchctl"

# --- verify ---
echo ""
echo "=== Status ==="
launchctl list | grep "$LABEL" || echo "  ✗ NOT FOUND in launchctl list"
echo ""
echo "Next fires daily at 06:00. Manual trigger:"
echo "  launchctl start $LABEL"
