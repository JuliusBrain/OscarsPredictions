#!/usr/bin/env python3
"""Compare the latest snapshot with the newest one at least 7 days older.

Writes docs/data/latest.json and docs/data/changes.json.
Per (category, film): status new | same | winner_gained | winner_lost.
"""
import json
import sys
from registry import build as build_registry
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SNAPS = ROOT / "data" / "snapshots"
OUT = ROOT / "docs" / "data"
OFFICIAL = ROOT / "data" / "official"


def load_snapshots(directory=SNAPS):
    snaps = [json.loads(p.read_text()) for p in sorted(directory.glob("*.json"))]
    return sorted(snaps, key=lambda s: s["date"])


def pick_baseline(snaps, latest, days=7):
    cutoff = date.fromisoformat(latest["date"]) - timedelta(days=days)
    older = [s for s in snaps if date.fromisoformat(s["date"]) <= cutoff]
    if older:
        return older[-1]
    earlier = [s for s in snaps if s["date"] < latest["date"]]
    return earlier[0] if earlier else None


def index(snap):
    return {(c, e["film"]): e for c, entries in snap["categories"].items() for e in entries}


def diff(latest, baseline):
    if baseline is None:
        return {"from": None, "to": latest["date"], "entries": {}, "dropped": []}
    old, new = index(baseline), index(latest)
    entries = {}
    for key, e in new.items():
        prev = old.get(key)
        if prev is None:
            status = "new"
        elif e["winner"] and not prev["winner"]:
            status = "winner_gained"
        elif prev["winner"] and not e["winner"]:
            status = "winner_lost"
        else:
            status = "same"
        entries[f"{key[0]}|{key[1]}"] = status
    dropped = [{"category": k[0], "film": k[1], "people": e["people"], "winner": e["winner"]}
               for k, e in old.items() if k not in new]
    return {"from": baseline["date"], "to": latest["date"], "entries": entries, "dropped": dropped}


def main():
    snaps = load_snapshots()
    if not snaps:
        sys.exit("no snapshots in data/snapshots")
    latest = snaps[-1]
    changes = diff(latest, pick_baseline(snaps, latest))
    OUT.mkdir(parents=True, exist_ok=True)
    official = load_snapshots(OFFICIAL) if OFFICIAL.exists() else []
    films_path = OUT / "films.json"
    existing = json.loads(films_path.read_text()) if films_path.exists() else None
    films_path.write_text(json.dumps(build_registry(snaps, official, existing), indent=1, ensure_ascii=False) + "\n")
    off_path = OUT / "official.json"
    if official:
        off_path.write_text(json.dumps(official[-1], indent=1, ensure_ascii=False) + "\n")
    elif off_path.exists():
        off_path.unlink()
    (OUT / "latest.json").write_text(json.dumps(latest, indent=1, ensure_ascii=False) + "\n")
    (OUT / "changes.json").write_text(json.dumps(changes, indent=1, ensure_ascii=False) + "\n")
    moved = sum(1 for v in changes["entries"].values() if v != "same")
    print(f"latest {latest['date']} vs {changes['from']}: {moved} changed, {len(changes['dropped'])} dropped")


if __name__ == "__main__":
    main()
