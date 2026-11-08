#!/usr/bin/env python3
"""Compare the latest snapshot with the newest one at least 7 days older.

Writes docs/data/latest.json and docs/data/changes.json.
"""
import json
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SNAPS = ROOT / "data" / "snapshots"
OUT = ROOT / "docs" / "data"


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
    return {
        (cat, e["film"]): e
        for cat, entries in snap["categories"].items()
        for e in entries
    }


def diff(latest, baseline):
    if baseline is None:
        return {"from": None, "to": latest["date"], "entries": {}, "dropped": []}
    old, new = index(baseline), index(latest)
    entries = {}
    for key, e in new.items():
        prev = old.get(key)
        if prev is None:
            status, delta = "new", None
        elif e["rank"] < prev["rank"]:
            status, delta = "up", prev["rank"] - e["rank"]
        elif e["rank"] > prev["rank"]:
            status, delta = "down", e["rank"] - prev["rank"]
        else:
            status, delta = "same", 0
        entries[f"{key[0]}|{key[1]}"] = {"status": status, "delta": delta,
                                          "prev_rank": prev["rank"] if prev else None}
    dropped = [
        {"category": k[0], "film": k[1], "people": e["people"], "rank": e["rank"]}
        for k, e in old.items() if k not in new
    ]
    return {"from": baseline["date"], "to": latest["date"],
            "entries": entries, "dropped": dropped}


def main():
    snaps = load_snapshots()
    if not snaps:
        sys.exit("no snapshots in data/snapshots")
    latest = snaps[-1]
    changes = diff(latest, pick_baseline(snaps, latest))
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "latest.json").write_text(json.dumps(latest, indent=1) + "\n")
    (OUT / "changes.json").write_text(json.dumps(changes, indent=1) + "\n")
    print(f"latest {latest['date']} vs {changes['from']}: "
          f"{len(changes['entries'])} entries, {len(changes['dropped'])} dropped")


if __name__ == "__main__":
    main()
