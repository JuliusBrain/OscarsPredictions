# Oscars Predictions

Personal tracker for the 2027 Oscars race: films against their nominations, categories, people, and what changed since last week. Live at https://juliusbrain.github.io/OscarsPredictions/ (served from `docs/` by GitHub Pages).

Ground truth is Variety's [2027 Oscars predictions](https://variety.com/lists/2027-oscars-predictions/): predicted nominees per category (listed alphabetically, not ranked) with the predicted winner marked.

## Themes
Two themes share one layout (top bar, hero with progress card, card rows): **Modern Light** (default) and **Deco Noir**. A theme only sets design tokens in `docs/styles.css` (palette, fonts, corner shapes, shadows). The choice is remembered per browser.

## Language and calendar
- **EN | PL switch** at the top of the page. All UI text lives in `docs/i18n.js`; `scripts/test_i18n.py` fails if a string is missing in either language. In Polish, film titles use Filmweb's Polish titles (the original is shown under it).
- **Calendar tab**: a month grid of Polish cinema premieres (dates from Filmweb) with a plan-to-watch list below it (upcoming first; already released and undated films are folded away). You can tick films as watched from the list.

## Daily update (runs on your Mac)
`scripts/daily-update.sh` downloads Variety's page with plain `wget` (its own user agent, one attempt), saves a snapshot **only if the predictions changed**, prints what changed (new, dropped, winner changes, and films still needing a Filmweb page), then commits and pushes. GitHub's workflow takes over from there: weekly diff, Filmweb dates, streaming data, deploy. It runs on your machine because Variety serves a normal download to a home connection; if it ever refuses (HTTP error) or the page layout changes, the script stops, tells you with a macOS notification, and does nothing else. It never retries or works around a block. Fall back to saving the page by hand and `/update-oscars`.

```bash
bash scripts/launchd/install.sh              # schedule it daily at 08:05 (a missed run happens when the Mac wakes)
launchctl kickstart -k gui/$(id -u)/com.oscars-tracker.daily   # run it now
DRY_RUN=1 bash scripts/daily-update.sh       # download and check only, no commit or push
bash scripts/launchd/install.sh --uninstall  # remove the schedule
```
Log: `~/Library/Logs/oscars-daily.log`. Needs `wget` (`brew install wget`) and your normal `git push` access.

## Updating from Variety
Variety can block automated readers (HTTP 402 via TollBit; it did for cloud tools), so this manual route is the fallback when the daily job reports a refusal:

1. Open the Variety page and use File > Save Page As (HTML) into `~/Downloads`.
2. In Claude Code, run `/update-oscars`. It copies the page to `data/inbox/` (gitignored), parses it into `data/snapshots/YYYY-MM-DD.json`, checks the counts, and commits and pushes.

Or by hand:
```bash
cp ~/Downloads/"2027 Oscars Predictions in Every Category.html" data/inbox/$(date +%F).html
python3 scripts/parse_variety.py && python3 scripts/diff.py
git add data/snapshots docs/data && git commit -m "Update Variety snapshot" && git push
```

## Where the data lives (the repo is the database)
| File | What it holds |
|---|---|
| `data/snapshots/*.json` | One parsed Variety snapshot per save. Never deleted. |
| `docs/data/films.json` | Film registry: every film ever on the list, with first/last seen dates and per-category history. A film that drops off Variety stays here (inactive) and is tagged NOMINATED if it later appears in the official nominees. Rebuilt by `scripts/diff.py` and merged with the existing file, so nothing is lost. |
| `data/official/YYYY-MM-DD.json` | Official Academy nominees (same format as a snapshot). Drop one in on Jan. 21, 2027 and the Official nominees tab fills in. |
| `docs/data/watched.json` | Your watched films, written by the site itself via the GitHub API. |

### Polish release dates and where to watch
Each film row shows its world premiere and Polish cinema date (from [Filmweb](https://www.filmweb.pl)) and where it can be watched in Poland.

- `data/filmweb-map.json` maps each film id to its Filmweb page. Filmweb's search is script-rendered, so new films are mapped by hand or by `/update-oscars`. `scripts/filmweb.py` then reads the public film and `/dates` pages (polite: one request at a time, 2 s apart, cached; settled films refresh weekly) into `docs/data/filmweb.json`.
- `scripts/availability.py` asks the [TMDB](https://www.themoviedb.org) API (watch-provider data by JustWatch) which Polish services stream, rent or sell each film. **This needs a free TMDB token**: create an account, open Settings > API, copy the *API Read Access Token*, then add it to this repo as the secret `TMDB_TOKEN` (`gh secret set TMDB_TOKEN`). Without it the site shows "not checked yet" and only the release-window estimate.
- When a film is not on any Polish service yet, the site shows an **estimate** (rent/buy about 6 to 13 weeks after the Polish cinema date, streaming about 3 to 6 months), or builds on a digital release date already set in another country. It is a guess from typical gaps, never an announcement.
- Filmweb itself loads its per-film streaming list through an undocumented internal API; this project does not use it.

### Saving watched marks to the repo
Open **Sync settings** on the site and paste a fine-grained GitHub token limited to this repo with **Contents: Read and write**. It stays in your browser and is only sent to api.github.com. Each tick commits `docs/data/watched.json` (about a second later), which redeploys the site. Without a token, marks stay in that browser only.

## How changes are tracked
`scripts/diff.py` compares the newest snapshot with the newest one at least 7 days older and writes `docs/data/changes.json` (new nominees, winner gained or lost, dropped). The workflow also runs daily so the window keeps rolling, and redeploys on every push.

## Local
```bash
python3 -m unittest discover -s scripts
python3 -m http.server -d docs
```
