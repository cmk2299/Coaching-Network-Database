#!/bin/bash
# Einmaliger Preload mit automatischer Selbstentfernung
# Läuft am 6. Feb 2026 um 3:00 Uhr

LOG_DIR="/Users/cmk/Documents/Football Coaches DB/tmp"
PLIST_PATH="$HOME/Library/LaunchAgents/com.footballdb.preload-once.plist"

echo "[$(date)] Starte einmaligen Preload aller Bundesliga-Trainer..." >> "$LOG_DIR/preload-once.log"

# Preload ausführen
cd "/Users/cmk/Documents/Football Coaches DB"
/usr/bin/python3 execution/preload_coach_data.py --force >> "$LOG_DIR/preload-once.log" 2>&1

echo "[$(date)] Preload abgeschlossen. Entferne einmaligen Job..." >> "$LOG_DIR/preload-once.log"

# Job entladen und löschen
launchctl unload "$PLIST_PATH" 2>/dev/null
rm -f "$PLIST_PATH"
rm -f "/Users/cmk/Documents/Football Coaches DB/com.footballdb.preload-once.plist"

echo "[$(date)] Einmaliger Job entfernt. Wöchentlicher Job läuft weiter." >> "$LOG_DIR/preload-once.log"
