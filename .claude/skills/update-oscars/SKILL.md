---
name: update-oscars
description: Ingest a freshly saved Variety "2027 Oscars Predictions in Every Category" page into the tracker, then commit and push so GitHub Pages redeploys. Use when the user says they saved the Variety page or runs /update-oscars.
---

# Update Oscars data

Variety blocks automated fetches (HTTP 402), so the user saves the page from their own browser. Never try to fetch variety.com directly.

1. Find the newest `*Oscars Predictions*.html` in `~/Downloads` (or use a path the user gives). If none, tell the user to open https://variety.com/lists/2027-oscars-predictions/ and use File > Save Page As (HTML), then stop.
2. Copy it to `data/inbox/<today YYYY-MM-DD>.html` (`data/inbox/*` is gitignored; the raw page is never committed).
3. Run `python3 scripts/parse_variety.py`. Sanity-check the output: 21 categories, 110 entries, exactly one `winner` per category. If a count is off or the parser errors, the page layout changed: show the user the problem and do not commit.
4. Run `python3 -m unittest discover -s scripts` and `python3 scripts/diff.py`.
5. `scripts/diff.py` also rebuilds `docs/data/films.json` (the film registry). Dropped films must stay in it as inactive: check the count of films did not shrink.
6. Summarize what changed vs the baseline (from `docs/data/changes.json`: new nominees, winner changes, dropped).
7. For every film id in `docs/data/films.json` that is missing from `data/filmweb-map.json`, find its Filmweb page with WebSearch (`allowed_domains: ["filmweb.pl"]`, query `filmweb <title> <year> film`), use only a URL that appeared in the results (the main film page, not /opinie, /dates or news), add it to `data/filmweb-map.json`, then run `python3 scripts/filmweb.py` and `python3 scripts/availability.py` and check each new film's `title_original`/`year` in `docs/data/filmweb.json` matches. Never bypass any blocking.
8. Commit `data/snapshots`, `data/filmweb-map.json` and `docs/data` (never touch `docs/data/watched.json`: the site writes it) with message `Update Variety snapshot <date>` and push to `main`. The workflow deploys the site.
