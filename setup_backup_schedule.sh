#!/bin/bash
# setup_backup_schedule.sh — Install the LaunchAgent that runs backup_data.sh daily
# at 03:30 (before the 06:00 daily-refresh). Closes the P0 DR gap: data/ (2GB
# scrape asset) is gitignored, so git is NOT a backup; a wipe already happened.
#
# Usage:
#   BACKUP_DEST=/Volumes/T7 bash setup_backup_schedule.sh   # external/offsite (recommended)
#   bash setup_backup_schedule.sh                            # local ~/coachdb-backups
#   bash setup_backup_schedule.sh --uninstall
#   bash setup_backup_schedule.sh --verify
#
# For TRUE disaster recovery set BACKUP_DEST to an external drive or remote host.
set -euo pipefail

BASE="/Users/cmk/Documents/CMK Digital/Football Coaches DB"
LABEL="com.footballdb.backup"
PLIST="$HOME/Library/LaunchAgents/${LABEL}.plist"
DEST="${BACKUP_DEST:-$HOME/coachdb-backups}"

case "${1:-install}" in
  --uninstall)
    launchctl unload "$PLIST" 2>/dev/null || true
    rm -f "$PLIST"; echo "✓ Removed $LABEL."; exit 0 ;;
  --verify)
    launchctl list | grep "footballdb.backup" || echo "  (not loaded)"
    ls -la "$PLIST" 2>/dev/null || echo "  (plist missing)"
    echo "Latest snapshots in $DEST:"; ls -1dt "$DEST"/*/ 2>/dev/null | head -3 || echo "  (none yet)"
    exit 0 ;;
esac

if [ ! -f "$BASE/backup_data.sh" ]; then
  echo "✗ Aborting: $BASE/backup_data.sh is missing." >&2; exit 1
fi

mkdir -p "$HOME/Library/LaunchAgents"
cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>${LABEL}</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>${BASE}/backup_data.sh</string>
    </array>
    <key>EnvironmentVariables</key>
    <dict><key>BACKUP_DEST</key><string>${DEST}</string></dict>
    <key>StartCalendarInterval</key>
    <dict><key>Hour</key><integer>3</integer><key>Minute</key><integer>30</integer></dict>
    <key>StandardOutPath</key><string>${BASE}/logs/backup.out.log</string>
    <key>StandardErrorPath</key><string>${BASE}/logs/backup.err.log</string>
    <key>WorkingDirectory</key><string>${BASE}</string>
</dict>
</plist>
EOF

mkdir -p "$BASE/logs"
launchctl unload "$PLIST" 2>/dev/null || true
launchctl load "$PLIST"
echo "✓ Installed $LABEL — daily 03:30 backup → $DEST"
echo "  Verify: bash setup_backup_schedule.sh --verify"
[ "$DEST" = "$HOME/coachdb-backups" ] && echo "  ⚠ Local dest = not offsite DR. Set BACKUP_DEST to an external/remote location."
