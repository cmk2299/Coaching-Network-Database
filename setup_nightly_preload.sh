#!/bin/bash
# Setup script for weekly pre-loader cron job
# Run this once to enable automatic weekly pre-loading every Sunday at 3 AM

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PRELOAD_SCRIPT="$SCRIPT_DIR/execution/preload_coach_data.py"
LOG_FILE="$SCRIPT_DIR/tmp/preload.log"

# Create tmp directory if it doesn't exist
mkdir -p "$SCRIPT_DIR/tmp"

# Cron job entry - runs every Sunday at 3 AM
# Format: minute hour day month weekday command
# 0 = Sunday
CRON_ENTRY="0 3 * * 0 cd $SCRIPT_DIR && /usr/bin/python3 $PRELOAD_SCRIPT >> $LOG_FILE 2>&1"

# Check if cron job already exists
if crontab -l 2>/dev/null | grep -q "preload_coach_data.py"; then
    echo "⚠️  Cron job already exists. Current crontab:"
    crontab -l | grep preload
    echo ""
    read -p "Replace existing job? (y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Aborted."
        exit 0
    fi
    # Remove existing entry
    crontab -l 2>/dev/null | grep -v "preload_coach_data.py" | crontab -
fi

# Add new cron job
(crontab -l 2>/dev/null; echo "$CRON_ENTRY") | crontab -

echo "✅ Cron job installed successfully!"
echo ""
echo "The pre-loader will run every SUNDAY at 3:00 AM"
echo "Log file: $LOG_FILE"
echo ""
echo "To check current cron jobs:"
echo "  crontab -l"
echo ""
echo "To remove the cron job:"
echo "  crontab -l | grep -v preload_coach_data.py | crontab -"
echo ""
echo "To run manually now (initial setup):"
echo "  python3 $PRELOAD_SCRIPT"
echo ""
echo "To run for a single coach:"
echo "  python3 $PRELOAD_SCRIPT --coach 'Alexander Blessin'"
