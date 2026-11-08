#!/usr/bin/env python3
"""Parse a saved Variety "Oscars Predictions in Every Category" page.

Reads data/inbox/YYYY-MM-DD.html and writes data/snapshots/YYYY-MM-DD.json.
The page lists each category's predicted nominees alphabetically and marks the
predicted winner with "***". Entries are either film-first (film line, then
credits) or person-first (person line, then film line).
"""
import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INBOX = ROOT / "data" / "inbox"
SNAPS = ROOT / "data" / "snapshots"

ARTICLE = re.compile(r'<article class="pmc-fallback-list-item">(.*?)</article>', re.S)
FILM = re.compile(
    r'^[“"](?P<title>.+?)[”"]'
    r'(?:\s+from\s+(?P<from>.+?))?'
    r'\s*\((?P<studio>[^()]+)\)\s*$')
STAR = re.compile(r'\s*\*{3}\s*')


def _lines(fragment):
    text = re.sub(r"<br\s*/?>", "\n", fragment)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text).replace("\xa0", " ")
    return [l.strip() for l in text.split("\n") if l.strip()]


def _names(line):
    line = re.sub(r"\(p\.g\.a\.\)", "", line)
    line = re.sub(r"^dir\.\s*", "", line.strip(), flags=re.I)
    parts = re.split(r",\s*|\s+and\s+", line)
    return [p.strip() for p in parts if p.strip()]


def _entry(m, winner, people):
    e = {"film": m.group("title").strip(), "studio": m.group("studio").strip(),
         "people": people, "winner": winner}
    src = m.group("from")
    if src:
        if src[0] in "“\"":  # song: "Song" from "Film"
            e["song"] = e["film"]
            e["film"] = src.strip("“”\" ")
        else:
            e["country"] = src.strip()
    return e


def parse_category(lines, title):
    first = FILM.match(STAR.sub("", lines[0]))
    film_first = first is not None
    entries, pending, pending_win = [], [], False
    for raw in lines:
        win = "***" in raw
        line = STAR.sub("", raw).strip()
        m = FILM.match(line)
        if m:
            if film_first:
                entries.append(_entry(m, win, []))
            else:
                entries.append(_entry(m, win or pending_win, pending))
                pending, pending_win = [], False
        elif film_first:
            if not entries:
                raise ValueError(f"{title}: credit before film: {raw!r}")
            entries[-1]["people"] += _names(line)
            entries[-1]["winner"] = entries[-1]["winner"] or win
        else:
            pending, pending_win = _names(line), win
    if pending:
        raise ValueError(f"{title}: person without film: {pending}")
    return entries


def parse_html(text, date):
    cats = {}
    for art in ARTICLE.findall(text):
        title = html.unescape(re.search(r"<h2>(.*?)</h2>", art, re.S).group(1)).strip()
        body = re.search(r'pmc-not-a-paywall">(.*?)</div>', art, re.S)
        if not body:
            continue
        para = re.search(r'<p class="paragraph[^>]*text-align-left[^>]*>(.*?)</p>',
                         body.group(1), re.S)
        lines = _lines(para.group(1) if para else body.group(1))
        if lines:
            cats[title] = parse_category(lines, title)
    if not cats:
        raise ValueError("no categories found: page layout may have changed")
    mod = re.search(r'article:modified_time" content="([^"]+)"', text)
    return {"date": date, "source": "variety",
            "source_updated": mod.group(1) if mod else None, "categories": cats}


def main():
    files = sorted(INBOX.glob("*.html"))
    if not files:
        sys.exit("data/inbox has no .html files")
    for path in files:
        snap = parse_html(path.read_text(encoding="utf-8", errors="replace"), path.stem)
        out = SNAPS / f"{path.stem}.json"
        out.write_text(json.dumps(snap, indent=1, ensure_ascii=False) + "\n")
        n = sum(len(v) for v in snap["categories"].values())
        print(f"{path.name} -> {out.relative_to(ROOT)}: {len(snap['categories'])} categories, {n} entries")


if __name__ == "__main__":
    main()
