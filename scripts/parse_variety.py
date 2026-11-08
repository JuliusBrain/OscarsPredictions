#!/usr/bin/env python3
"""Turn files in data/inbox/ into snapshots in data/snapshots/.

Current input: plain text saved by hand from the Variety page, named
YYYY-MM-DD.txt, in this shape (rank order = line order):

    # Picture
    1. Film Title
    # Actor
    1. Film Title - Person Name, Other Person

Saved HTML (.html) is not parsed yet: it needs a real sample of the page to
write selectors against. Add parse_html() once one exists.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INBOX = ROOT / "data" / "inbox"
SNAPS = ROOT / "data" / "snapshots"
LINE = re.compile(r"^\s*(\d+)[.)]\s+(.+?)(?:\s+[-–—]\s+(.+))?\s*$")


def parse_text(text, date, source="variety"):
    cats, current = {}, None
    for raw in text.splitlines():
        if not raw.strip():
            continue
        if raw.lstrip().startswith("#"):
            current = raw.lstrip("# ").strip()
            cats[current] = []
            continue
        m = LINE.match(raw)
        if not m or current is None:
            raise ValueError(f"unparseable line: {raw!r}")
        people = [p.strip() for p in (m.group(3) or "").split(",") if p.strip()]
        cats[current].append({"rank": int(m.group(1)), "film": m.group(2).strip(),
                              "people": people})
    return {"date": date, "source": source, "categories": cats}


def main():
    for path in sorted(INBOX.glob("*.txt")):
        out = SNAPS / f"{path.stem}.json"
        snap = parse_text(path.read_text(), path.stem)
        out.write_text(json.dumps(snap, indent=1) + "\n")
        print(f"{path.name} -> {out.relative_to(ROOT)}")
    if not list(INBOX.glob("*.txt")):
        print("inbox empty", file=sys.stderr)


if __name__ == "__main__":
    main()
