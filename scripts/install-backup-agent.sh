#!/usr/bin/env bash
# Installs the daily 09:00 SQLite backup as a macOS launchd user agent.
#
# This script is NOT run automatically by anything in this repo — run it
# yourself when you're ready to enable the daily backup:
#
#   ./scripts/install-backup-agent.sh
set -euo pipefail

PLIST_NAME="com.pj.budgeting-backup.plist"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="$SCRIPT_DIR/$PLIST_NAME"
DEST="$HOME/Library/LaunchAgents/$PLIST_NAME"

if [ ! -f "$SRC" ]; then
    echo "Cannot find $SRC" >&2
    exit 1
fi

mkdir -p "$HOME/Library/LaunchAgents"
mkdir -p "$HOME/.budgeting-app/backups"

cp "$SRC" "$DEST"

# Unload first so re-running this script picks up plist edits.
launchctl unload "$DEST" 2>/dev/null || true
launchctl load "$DEST"

echo "Installed and loaded $DEST"
echo "Runs daily at 09:00. Check status with: launchctl list | grep com.pj.budgeting-backup"
echo "Logs: ~/.budgeting-app/backups/launchd.log and launchd.error.log"
echo "To uninstall: launchctl unload $DEST && rm $DEST"
