#!/usr/bin/env python3
"""Where each film can be watched in Poland, plus a labelled estimate when it is not out yet.

Providers and digital release dates come from the TMDB API (watch-provider data
is supplied by JustWatch). Needs a free TMDB "API Read Access Token" in the
TMDB_TOKEN environment variable; without it, provider checks are skipped and
only the estimate is written. Estimates are derived from the Polish cinema
date (Filmweb) and, when known, a digital release date elsewhere; they are
guesses from typical release windows, never announcements.
"""
import json
import os
import re
import unicodedata
import sys
import time
import urllib.parse
import urllib.request
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FILMWEB = ROOT / "docs" / "data" / "filmweb.json"
FILMS = ROOT / "docs" / "data" / "films.json"
TMDB_MAP = ROOT / "data" / "tmdb-map.json"
OVERRIDES = ROOT / "data" / "tmdb-overrides.json"
OUT = ROOT / "docs" / "data" / "availability.json"

# Typical gaps after the Polish cinema release (days). Heuristic, not a promise.
RENT_BUY = (45, 90)
STREAMING = (90, 180)


def _d(iso):
    return date.fromisoformat(iso)


def estimate(pl_cinema, world_premiere, digital_hint=None):
    """Return {rent_buy:[from,to], streaming:[from,to], basis} or None."""
    # No Polish release date and no known digital date: too little to estimate from.
    base = _d(pl_cinema) if pl_cinema else (_d(digital_hint["date"]) - timedelta(days=60) if digital_hint else None)
    if base is None:
        return None
    if digital_hint:
        h = _d(digital_hint["date"])
        rent = (h, h + timedelta(days=30))
        stream = (max(base + timedelta(days=STREAMING[0]), h + timedelta(days=30)), max(base + timedelta(days=STREAMING[1]), h + timedelta(days=120)))
        basis = (f"A digital release is already dated {digital_hint['date']} in {digital_hint['country']}; "
                 "Poland usually gets rent/buy within about a month of that, and subscription streaming a few months later.")
    else:
        rent = (base + timedelta(days=RENT_BUY[0]), base + timedelta(days=RENT_BUY[1]))
        stream = (base + timedelta(days=STREAMING[0]), base + timedelta(days=STREAMING[1]))
        basis = ("Typical gap after the Polish cinema release: rent/buy about 6 to 13 weeks, "
                 "subscription streaming about 3 to 6 months.")
    return {"rent_buy": [rent[0].isoformat(), rent[1].isoformat()],
            "streaming": [stream[0].isoformat(), stream[1].isoformat()], "basis": basis}


def parse_providers(payload):
    pl = (payload.get("results") or {}).get("PL") or {}
    out = {k: sorted({p["provider_name"] for p in pl.get(k, [])}) for k in ("flatrate", "rent", "buy", "ads", "free")}
    return {"providers": out, "link": pl.get("link")}


def parse_release_dates(payload):
    """Earliest digital (type 4) date overall, and Poland's digital date if any."""
    best, pl_digital = None, None
    for c in payload.get("results") or []:
        for r in c.get("release_dates", []):
            if r.get("type") == 4 and r.get("release_date"):
                d = r["release_date"][:10]
                if c.get("iso_3166_1") == "PL" and (pl_digital is None or d < pl_digital):
                    pl_digital = d
                if best is None or d < best["date"]:
                    best = {"date": d, "country": c.get("iso_3166_1")}
    return best, pl_digital


DATE_TOLERANCE_DAYS = 240  # festival premiere vs wide release can be months apart


def date_ok(release, ref):
    """TMDB release date must be near Filmweb's date; unknown dates cannot rule a match out."""
    if not release or not ref:
        return True
    return abs((_d(release[:10]) - _d(ref)).days) <= DATE_TOLERANCE_DAYS


def norm(text):
    ascii_text = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "", ascii_text.lower())


def pick_match(results, year, ref=None, names=None):
    """Best candidate whose year and date fit, and whose title equals one of our known titles.
    Requiring the title stops look-alikes ('The Wicker Children' for 'Wicker') being accepted."""
    names = {norm(n) for n in (names or []) if n}
    for r in sorted(results, key=lambda r: -(r.get("popularity") or 0)):
        rel = r.get("release_date") or ""
        year_ok = year is None or (rel[:4].isdigit() and abs(int(rel[:4]) - year) <= 1)
        title_ok = not names or norm(r.get("title")) in names or norm(r.get("original_title")) in names
        if year_ok and title_ok and date_ok(rel, ref):
            return r
    return None


def tmdb_get_factory(token):
    def get(path, **params):
        url = "https://api.themoviedb.org/3" + path + ("?" + urllib.parse.urlencode(params) if params else "")
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}", "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    return get


def resolve(get, queries, year, ref, cached=None, override=None):
    """Return (tmdb_id, title, release_date, candidates). Cached ids are re-validated;
    an id in data/tmdb-overrides.json is trusted as a manual correction."""
    if override:
        d = get(f"/movie/{override}")
        return override, d.get("title"), d.get("release_date"), []
    if cached:
        d = get(f"/movie/{cached}")
        names = {norm(q) for q in queries if q}
        if date_ok(d.get("release_date"), ref) and (not names or norm(d.get("title")) in names or norm(d.get("original_title")) in names):
            return cached, d.get("title"), d.get("release_date"), []
    seen = []
    for q in dict.fromkeys(x for x in queries if x):
        results = get("/search/movie", query=q).get("results", [])
        m = pick_match(results, year, ref, queries)
        if m:
            return m["id"], m.get("title"), m.get("release_date"), []
        seen += [{"id": r["id"], "title": r.get("title"), "release_date": r.get("release_date")} for r in results[:3]]
    return None, None, None, seen[:5]


def check_film(get, queries, year, ref=None, cached=None, override=None):
    tmdb_id, title, rel, cands = resolve(get, queries, year, ref, cached, override)
    if tmdb_id is None:
        return {"tmdb_id": None, "unmatched": True, "candidates": cands}
    prov = parse_providers(get(f"/movie/{tmdb_id}/watch/providers"))
    hint, pl_digital = parse_release_dates(get(f"/movie/{tmdb_id}/release_dates"))
    return {"tmdb_id": tmdb_id, "tmdb_title": title, "tmdb_release_date": rel, "providers": prov["providers"],
            "link": prov["link"], "digital_hint": hint, "pl_digital": pl_digital, "checked": date.today().isoformat()}


def main():
    fw = json.loads(FILMWEB.read_text()) if FILMWEB.exists() else {}
    films = json.loads(FILMS.read_text())["films"]
    tmap = json.loads(TMDB_MAP.read_text()) if TMDB_MAP.exists() else {}
    overrides = json.loads(OVERRIDES.read_text()) if OVERRIDES.exists() else {}
    old = json.loads(OUT.read_text())["films"] if OUT.exists() else {}
    token = os.environ.get("TMDB_TOKEN", "").strip()
    get = tmdb_get_factory(token) if token else None
    out = {}
    for fid, f in sorted(films.items()):
        rec = dict(old.get(fid, {}))
        if get and f.get("active", True):
            try:
                w0 = fw.get(fid) or {}
                res = check_film(get, [f["name"], w0.get("title_original"), w0.get("title_pl")], w0.get("year"),
                                 w0.get("world_premiere") or w0.get("pl_cinema"), tmap.get(fid), overrides.get(fid))
                for stale in ("providers", "link", "digital_hint", "pl_digital", "checked", "tmdb_title", "tmdb_release_date", "candidates", "unmatched"):
                    rec.pop(stale, None)  # an unmatched film must not keep an earlier wrong match's data
                if res.get("tmdb_id"):
                    tmap[fid] = res["tmdb_id"]
                else:
                    tmap.pop(fid, None)
                rec.update(res)
                time.sleep(0.3)
            except Exception as e:
                print(f"{fid}: TMDB failed ({e})", file=sys.stderr)
        w = fw.get(fid) or {}
        rec["estimate"] = estimate(w.get("pl_cinema"), w.get("world_premiere"), rec.get("digital_hint"))
        out[fid] = rec
    OUT.write_text(json.dumps({"generated": date.today().isoformat(), "tmdb_enabled": bool(token), "films": out},
                              indent=1, ensure_ascii=False) + "\n")
    if token:
        TMDB_MAP.write_text(json.dumps(dict(sorted(tmap.items())), indent=1) + "\n")
    print(f"availability: {len(out)} films, tmdb={'on' if token else 'off (no TMDB_TOKEN)'}")


if __name__ == "__main__":
    main()
