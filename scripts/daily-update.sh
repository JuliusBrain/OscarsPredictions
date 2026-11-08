#!/usr/bin/env bash
# Daily update, run on THIS machine (Variety answers a normal download from a home connection).
#   1. download Variety's predictions page with plain wget (its own user agent, one try, no workarounds)
#   2. record a snapshot only if the predictions changed, and print what changed
#   3. commit + push the snapshot; GitHub then rebuilds the diff, Filmweb dates, streaming data and the site
# If Variety refuses or the page looks wrong, it stops and tells you. It never retries or works around a block.
# Env: DRY_RUN=1 (download + check only, no commit/push/notification), NOTIFY=0, VARIETY_URL (for testing).
set -uo pipefail
cd "$(dirname "$0")/.."
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

URL="${VARIETY_URL:-https://variety.com/lists/2027-oscars-predictions/}"
TODAY="$(date +%F)"
TMP="$(mktemp -t variety.XXXXXX)"
trap 'rm -f "$TMP"' EXIT

notify() {  # macOS notification; silent elsewhere or in a dry run
  [ -n "${DRY_RUN:-}" ] && return 0
  [ "${NOTIFY:-1}" = "0" ] && return 0
  command -v osascript >/dev/null 2>&1 || return 0
  osascript -e "display notification \"${2//\"/}\" with title \"${1//\"/}\"" >/dev/null 2>&1 || true
}

if ! wget -q --timeout=30 --tries=1 -O "$TMP" "$URL"; then
  echo "[$TODAY] Download failed or was refused. Not retrying and not working around it." >&2
  notify "Oscars tracker" "Variety download failed. Save the page by hand and run /update-oscars."
  exit 1
fi

mkdir -p data/inbox
cp "$TMP" "data/inbox/$TODAY.html"               # local copy (gitignored); kept 30 days
find data/inbox -name '*.html' -mtime +30 -delete 2>/dev/null || true

OUT="$(python3 scripts/ingest_variety.py "$TMP" --date "$TODAY")"
RC=$?
echo "[$TODAY] $OUT"
case $RC in
  0)  exit 0 ;;                                   # nothing changed
  10) ;;                                          # new snapshot written
  *)  notify "Oscars tracker" "Variety page looked different (layout changed?). Nothing was saved."
      exit 1 ;;
esac

if [ -n "${DRY_RUN:-}" ]; then echo "[DRY RUN] would commit and push data/snapshots/$TODAY.json"; exit 0; fi

git pull --rebase --autostash -q origin main || { notify "Oscars tracker" "git pull failed; snapshot not pushed."; exit 1; }
git add data/snapshots
git commit -q -m "Update Variety snapshot $TODAY" -m "$OUT"
git push -q origin main || { notify "Oscars tracker" "git push failed; snapshot saved locally."; exit 1; }
notify "Oscars predictions changed" "$(echo "$OUT" | sed -n '1p')"
