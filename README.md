# Oscars Predictions

Personal tracker for the 2027 Oscars race: films against their nominations, categories, people, and what changed since last week. Live at https://juliusbrain.github.io/OscarsPredictions/ (served from `docs/` by GitHub Pages).

Ground truth is Variety's [2027 Oscars predictions](https://variety.com/lists/2027-oscars-predictions/): predicted nominees per category (listed alphabetically, not ranked) with the predicted winner marked.

## Updating from Variety
Variety blocks automated readers (HTTP 402 via TollBit), so the page is saved by hand from your own browser:

1. Open the Variety page and use File > Save Page As (HTML) into `~/Downloads`.
2. In Claude Code, run `/update-oscars`. It copies the page to `data/inbox/` (gitignored), parses it into `data/snapshots/YYYY-MM-DD.json`, checks the counts, and commits and pushes.

Or by hand:
```bash
cp ~/Downloads/"2027 Oscars Predictions in Every Category.html" data/inbox/$(date +%F).html
python3 scripts/parse_variety.py && python3 scripts/diff.py
git add data/snapshots docs/data && git commit -m "Update Variety snapshot" && git push
```

## How changes are tracked
`scripts/diff.py` compares the newest snapshot with the newest one at least 7 days older and writes `docs/data/changes.json` (new nominees, winner gained or lost, dropped). The workflow also runs daily so the window keeps rolling, and redeploys on every push.

## Local
```bash
python3 -m unittest discover -s scripts
python3 -m http.server -d docs
```
