#!/usr/bin/env bash
# Installs (or removes with --uninstall) the daily 08:05 job for the current user. Run it yourself:
#   bash scripts/launchd/install.sh            # install
#   bash scripts/launchd/install.sh --uninstall
set -euo pipefail
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
LABEL="com.oscars-tracker.daily"
DEST="$HOME/Library/LaunchAgents/$LABEL.plist"
if [ "${1:-}" = "--uninstall" ]; then
  launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
  rm -f "$DEST"; echo "Removed $LABEL"; exit 0
fi
mkdir -p "$HOME/Library/LaunchAgents" "$HOME/Library/Logs"
sed -e "s|__REPO__|$REPO|g" -e "s|__HOME__|$HOME|g" "$REPO/scripts/launchd/$LABEL.plist" > "$DEST"
launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$DEST"
echo "Installed: runs daily at 08:05 (a missed run happens when the Mac wakes). Log: ~/Library/Logs/oscars-daily.log"
echo "Run it now to test:  launchctl kickstart -k gui/$(id -u)/$LABEL"
