# Oscars Predictions

Personal tracker for the 2027 Oscars race: films by category, performers, and what changed since last week. Served from `docs/` via GitHub Pages.

## Updating the ground truth (Variety)
Variety blocks automated readers (HTTP 402 via TollBit), so the list is added by hand:

1. Open https://variety.com/lists/2027-oscars-predictions/ in your browser.
2. Save the rankings as `data/inbox/YYYY-MM-DD.txt`:
   ```
   # Picture
   1. Film Title
   # Actor
   1. Film Title - Person Name
   ```
3. Push. The workflow parses it into `data/snapshots/`, diffs against the newest snapshot at least 7 days older, and redeploys. It also runs daily so the weekly window keeps rolling.

The data currently in `data/snapshots/` is placeholder.

## Local
```bash
python3 -m unittest discover -s scripts
python3 scripts/diff.py
python3 -m http.server -d docs
```
