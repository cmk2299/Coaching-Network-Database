#!/usr/bin/env bash
# ───────────────────────────────────────────────────────────────────────────
# Backup the irreplaceable data asset (the ~100h Transfermarkt scrape) + the
# orchestration scripts. data/ is gitignored (data/*.json), so git is NOT a
# backup for it — a full wipe already happened once (2026-05-21, see memory).
#
#   bash backup_data.sh                 # → $HOME/coachdb-backups/<timestamp>/
#   BACKUP_DEST=/Volumes/T7 bash backup_data.sh         # external drive
#   BACKUP_DEST=user@host:/backups bash backup_data.sh  # offsite via rsync/ssh
#
# Keeps the last KEEP (default 7) local snapshots. For true DR, point BACKUP_DEST
# at an external drive or remote host (offsite), and schedule via cron/LaunchAgent.
# ───────────────────────────────────────────────────────────────────────────
set -uo pipefail
cd "$(dirname "$0")"
BASE="$(pwd)"

STAMP="$(date +%Y%m%d_%H%M%S)"
DEST="${BACKUP_DEST:-$HOME/coachdb-backups}"
KEEP="${KEEP:-7}"

# What to back up: the scraped asset + configs + scripts. Excludes regenerable
# caches (tmp/cache is ~13GB of re-fetchable HTML) and generated output/.
INCLUDE=(data execution directives *.sh *.md requirements.txt)
EXCLUDES=(--exclude ".DS_Store" --exclude "__pycache__" --exclude "*.pyc")

is_remote() { [[ "$DEST" == *:* && "$DEST" != /* && "$DEST" != .* ]]; }

if is_remote; then
  TARGET="$DEST/coachdb_$STAMP"
  echo "→ Offsite backup to $TARGET"
  rsync -az --delete "${EXCLUDES[@]}" "${INCLUDE[@]}" "$TARGET/" \
    || { echo "✗ rsync to $DEST failed"; exit 1; }
else
  TARGET="$DEST/$STAMP"
  mkdir -p "$TARGET" || { echo "✗ cannot create $TARGET"; exit 1; }
  echo "→ Local backup to $TARGET"
  rsync -a "${EXCLUDES[@]}" "${INCLUDE[@]}" "$TARGET/" \
    || { echo "✗ rsync failed"; exit 1; }
  # Retention: keep newest $KEEP timestamped snapshots
  ls -1dt "$DEST"/*/ 2>/dev/null | tail -n +$((KEEP + 1)) | while read -r old; do
    echo "  pruning old snapshot: $old"; rm -rf "$old"
  done
fi

SIZE=$(du -sh "$TARGET" 2>/dev/null | cut -f1)
echo "✓ Backup complete: $TARGET ($SIZE)"
echo "  Reminder: for real disaster recovery, set BACKUP_DEST to an EXTERNAL or"
echo "  OFFSITE location and schedule this (cron/LaunchAgent). Local-only ≠ DR."
