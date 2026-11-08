#!/usr/bin/env python3
"""World-premiere and Polish release dates from public Filmweb film pages.

Reads data/filmweb-map.json ({film_id: filmweb_url}), fetches each film's main
page and /dates page, and writes docs/data/filmweb.json. Filmweb's robots.txt
allows general crawling; requests are sequential, delayed, identify this
project, and are cached: a record is refetched only while the Polish release
is still upcoming/unknown or when it is older than REFRESH_DAYS.
"""
import html
import json
import re
import sys
import time
import urllib.request
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAP = ROOT / "data" / "filmweb-map.json"
OUT = ROOT / "docs" / "data" / "filmweb.json"
UA = "OscarsPredictionsTracker/1.0 (personal project; https://github.com/JuliusBrain/OscarsPredictions)"
DELAY = 2.0
REFRESH_DAYS = 7
MONTHS = {"stycznia": 1, "lutego": 2, "marca": 3, "kwietnia": 4, "maja": 5, "czerwca": 6, "lipca": 7,
          "sierpnia": 8, "września": 9, "października": 10, "listopada": 11, "grudnia": 12}


def parse_pl_date(text):
    m = re.search(r"(\d{1,2})\s+([a-ząćęłńóśźż]+)\s+(\d{4})", text.lower())
    if not m or m.group(2) not in MONTHS:
        return None
    return date(int(m.group(3)), MONTHS[m.group(2)], int(m.group(1))).isoformat()


def parse_main(page):
    g = re.search(r'globalPremiereDate:\s*"([^"]*)"', page)
    l = re.search(r'localPremiereDate:\s*"([^"]*)"', page)
    t = re.search(r'<h1 class="filmCoverSection__title[^"]*"[^>]*>([^<]*)<', page)
    o = re.search(r'filmCoverSection__originalTitle">([^<]*)<', page)
    y = re.search(r'filmCoverSection__year">(\d{4})', page)
    return {"world_premiere": (g.group(1) or None) if g else None,
            "pl_cinema_main": (l.group(1) or None) if l else None,
            "title_pl": html.unescape(t.group(1)).strip() if t else None,
            "title_original": html.unescape(o.group(1)).strip() if o else None,
            "year": int(y.group(1)) if y else None}


def parse_dates(page):
    out = []
    for item in re.findall(r'<li class="filmDatesSection__item".*?</li>', page, re.S):
        title = re.search(r'filmDatesSection__title">(.*?)</div>', item, re.S)
        cc = re.search(r"entity@country:([A-Z]{2})", item)
        desc = re.search(r'filmDatesSection__desc">(.*?)</div>', item, re.S)
        note = re.search(r"\(([^)]+)\)", html.unescape(re.sub(r"<[^>]+>", " ", desc.group(1)))) if desc else None
        iso = parse_pl_date(title.group(1)) if title else None
        if iso and cc:
            out.append({"date": iso, "country": cc.group(1), "note": note.group(1) if note else None})
    return out


def poland_cinema(dates):
    """Earliest Polish date from the /dates page, ignoring festival/premiere-only notes."""
    pl = [d for d in dates if d["country"] == "PL"]
    normal = [d for d in pl if not d["note"] or "festiwal" not in d["note"].lower()]
    pool = normal or pl
    return min((d["date"] for d in pool), default=None)


ISO = re.compile(r"\d{4}-\d{2}-\d{2}$")


def normalize(rec):
    """Filmweb omits the original title when it equals the Polish one, and sometimes
    gives only a year as the world-premiere date. Keep both cases explicit."""
    rec = dict(rec)
    rec["title_original"] = rec.get("title_original") or rec.get("title_pl")
    for key in ("world_premiere", "pl_cinema_main", "pl_cinema"):
        v = rec.get(key)
        if v and not ISO.match(v):
            if key == "world_premiere" and re.fullmatch(r"\d{4}", v):
                rec["world_premiere_year"] = int(v)
            rec[key] = None
    return rec


def build_record(url, main_html, dates_html, today):
    rec = parse_main(main_html)
    dates = parse_dates(dates_html) if dates_html else []
    rec["pl_cinema"] = poland_cinema(dates) or rec["pl_cinema_main"]
    rec["dates_conflict"] = bool(rec["pl_cinema_main"] and rec["pl_cinema"] and rec["pl_cinema_main"] != rec["pl_cinema"])
    if not rec["world_premiere"] and dates:
        rec["world_premiere"] = min(d["date"] for d in dates)
    rec.update({"url": url, "fetched": today.isoformat(), "stale": False})
    return normalize(rec)


def needs_refresh(rec, today):
    if not rec or rec.get("stale") or not rec.get("pl_cinema"):
        return True
    if rec["pl_cinema"] > today.isoformat():
        return True
    return date.fromisoformat(rec["fetched"]) <= today - timedelta(days=REFRESH_DAYS)


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "pl"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def main():
    mapping = json.loads(MAP.read_text())
    existing = json.loads(OUT.read_text()) if OUT.exists() else {}
    today, out, fetched = date.today(), {}, 0
    for fid, url in sorted(mapping.items()):
        if not url:
            continue
        old = existing.get(fid)
        if not needs_refresh(old, today):
            out[fid] = normalize(old)
            continue
        try:
            main_html = fetch(url)
            time.sleep(DELAY)
            dates_html = fetch(url.rstrip("/") + "/dates")
            time.sleep(DELAY)
            out[fid] = build_record(url, main_html, dates_html, today)
            fetched += 1
        except Exception as e:  # keep the last good record, flag it stale
            print(f"{fid}: fetch failed ({e})", file=sys.stderr)
            if old:
                out[fid] = dict(old, stale=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(dict(sorted(out.items())), indent=1, ensure_ascii=False) + "\n")
    print(f"filmweb: {len(out)} films, {fetched} fetched")


if __name__ == "__main__":
    main()
