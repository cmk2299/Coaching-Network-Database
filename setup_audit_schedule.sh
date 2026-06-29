#!/bin/bash
# setup_audit_schedule.sh — Install the LaunchAgent that runs run_audit_loop.sh
# nightly at 02:30 (before backup 03:30 + daily refresh 06:00). Continuous drift
# detection: any LOGIC or SCORING regression in data/networks/*.json gets logged
# overnight so the morning refresh starts with a clean signal.
#
# Usage:
#   bash setup_audit_schedule.sh                          # install + load
#   bash setup_audit_schedule.sh --uninstall
#   bash setup_audit_schedule.sh --verify
#
# Output: logs/audit.{out,err}.log (rolling, gitignored).

set -euo pipefail
BASE="/Users/cmk/Documents/CMK Digital/Football Coaches DB"
LABEL="com.footballdb.audit-loop"
PLIST="$HOME/Library/LaunchAgents/${LABEL}.plist"

case "${1:-install}" in
  --uninstall)
    launchctl unload "$PLIST" 2>/dev/null || true
    rm -f "$PLIST"; echo "✓ Removed $LABEL."; exit 0 ;;
  --verify)
    launchctl list | grep "footballdb.audit-loop" || echo "  (not loaded)"
    ls -la "$PLIST" 2>/dev/null || echo "  (plist missing)"
    echo "Latest audit logs:"
    ls -1t "$BASE/logs"/audit*.log 2>/dev/null | head -3
    exit 0 ;;
esac

if [ ! -f "$BASE/run_audit_loop.sh" ]; then
  echo "✗ Aborting: $BASE/run_audit_loop.sh is missing." >&2; exit 1
fi

mkdir -p "$HOME/Library/LaunchAgents" "$BASE/logs"
cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>${LABEL}</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>${BASE}/run_audit_loop.sh</string>
        <string>500</string>
        <string>3</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict><key>Hour</key><integer>2</integer><key>Minute</key><integer>30</integer></dict>
    <key>StandardOutPath</key><string>${BASE}/logs/audit.out.log</string>
    <key>StandardErrorPath</key><string>${BASE}/logs/audit.err.log</string>
    <key>WorkingDirectory</key><string>${BASE}</string>
</dict>
</plist>
EOF

launchctl unload "$PLIST" 2>/dev/null || true
launchctl load "$PLIST"
echo "✓ Installed $LABEL — nightly 02:30 audit (500-sample × 3 rounds)"
echo "  Verify:  bash setup_audit_schedule.sh --verify"
echo "  Logs:    $BASE/logs/audit.{out,err}.log"
