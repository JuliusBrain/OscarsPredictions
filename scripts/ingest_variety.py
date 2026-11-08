#!/usr/bin/env python3
"""Turn a freshly downloaded Variety page into a snapshot, only when predictions changed.

    python3 scripts/ingest_variety.py page.html [--date YYYY-MM-DD]

Exit codes: 0 = nothing changed, 10 = new snapshot written, 2 = page invalid
(layout changed or not the real page). Prints a short human-readable change list.
"""
import argparse
import json
import sys
from datetime import date as _date
from pathlib import Path

from diff import index, load_snapshots
from parse_variety import ROOT, SNAPS, parse_html
from registry import slug

MIN_CATEGORIES = 15  # the real page has 21; fewer means a block page or a layout change


def summarize(old, new, limit=40):
    """Human-readable differences between two snapshots (not the 7-day window)."""
    if old is None:
        return ["First snapshot recorded."]
    a, b = index(old), index(new)
    lines = []
    for key, e in sorted(b.items()):
        prev = a.get(key)
        cat, film = key
        if prev is None:
            lines.append(f"NEW: {film} in {cat}" + (" (predicted winner)" if e["winner"] else ""))
        elif e["winner"] and not prev["winner"]:
            lines.append(f"WINNER: {film} is now the predicted winner in {cat}")
        elif prev["winner"] and not e["winner"]:
            lines.append(f"NOT WINNER: {film} is no longer the predicted winner in {cat}")
    for key in sorted(a):
        if key not in b:
            lines.append(f"DROPPED: {key[1]} from {key[0]}")
    if len(lines) > limit:
        lines = lines[:limit] + [f"... and {len(lines) - limit} more"]
    return lines


def unmapped_films(snap, mapping):
    """Films in the snapshot that have no Filmweb page in data/filmweb-map.json yet."""
    names = {e["film"] for entries in snap["categories"].values() for e in entries}
    return sorted(n for n in names if not mapping.get(slug(n)))


def ingest(html_text, day, snaps_dir=SNAPS, min_categories=MIN_CATEGORIES):
    snap = parse_html(html_text, day)  # raises ValueError if no categories
    if len(snap["categories"]) < min_categories:
        raise ValueError(f"only {len(snap['categories'])} categories found (expected about 21)")
    snaps = load_snapshots(snaps_dir)
    latest = snaps[-1] if snaps else None
    if latest and latest["categories"] == snap["categories"]:
        return {"status": "unchanged", "lines": [], "path": None}
    lines = summarize(latest, snap)
    path = Path(snaps_dir) / f"{day}.json"
    path.write_text(json.dumps(snap, indent=1, ensure_ascii=False) + "\n")
    return {"status": "new", "lines": lines, "path": str(path)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("html")
    ap.add_argument("--date", default=_date.today().isoformat())
    args = ap.parse_args()
    try:
        text = Path(args.html).read_text(encoding="utf-8", errors="replace")
        result = ingest(text, args.date)
    except ValueError as e:
        print(f"Page not usable: {e}", file=sys.stderr)
        sys.exit(2)
    if result["status"] == "unchanged":
        print("No changes in Variety's predictions.")
        sys.exit(0)
    print(f"Predictions changed ({len(result['lines'])} differences):")
    for line in result["lines"]:
        print("  " + line)
    map_path = ROOT / "data" / "filmweb-map.json"
    if map_path.exists():
        missing = unmapped_films(json.loads(Path(result["path"]).read_text()), json.loads(map_path.read_text()))
        if missing:
            print("Needs a Filmweb page (run /update-oscars to map): " + ", ".join(missing))
    sys.exit(10)


if __name__ == "__main__":
    main()
