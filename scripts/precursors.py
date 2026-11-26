#!/usr/bin/env python3
"""Precursor awards (Golden Globes, Critics' Choice, BAFTA, ...) for the tracked films.

Wikipedia first: every event has a page whose category sections list nominees
with the winner in bold. Pages are fetched through the MediaWiki API (polite
User-Agent, maxlag, backoff on 429). Where Wikipedia has nothing usable, an
event can name a parser in OFFICIAL_PARSERS; none are registered yet because
each official site needs its own, checked against the live markup.

Output: docs/data/precursors.json
  events:  [{id, name, short, status: pending|nominees|winners, source, url, categories:[...]}]
  by_film: {film_id: [{event, category, oscar, winner}]}
If a fetch fails, the previous result for that event is kept and marked stale.
"""
import json
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EVENTS = ROOT / "data" / "precursors" / "events.json"
FILMS = ROOT / "docs" / "data" / "films.json"
OUT = ROOT / "docs" / "data" / "precursors.json"
UA = "OscarsPredictionsTracker/1.0 (https://github.com/JuliusBrain/OscarsPredictions)"
API = "https://en.wikipedia.org/w/api.php"

OFFICIAL_PARSERS = {}  # name -> callable(event) -> categories list (see parse_wikipedia output)

# Event category label -> the Oscar category it predicts. First match wins.
OSCAR_RULES = [
    (r"supporting.*(actress|female)|(female|actress).*supporting", "Supporting Actress"),
    (r"supporting.*(actor|male)|(male|actor).*supporting", "Supporting Actor"),
    (r"actress|female actor|lead(ing)? (female|actress)|actor in a leading role.*female", "Actress"),
    (r"\bactor\b|male actor|lead(ing)? (male|actor)", "Actor"),
    (r"director|directing", "Directing"),
    (r"original screenplay|original script", "Original Screenplay"),
    (r"adapted screenplay|adapted script", "Adapted Screenplay"),
    (r"screenplay|writing|script", "Screenplay"),
    (r"documentary", "Documentary Feature"),
    (r"international|foreign|non-english|not in the english", "International Feature"),
    (r"animated", "Animated Feature"),
    (r"best (motion )?picture|best film(?! not)|best feature|outstanding .*motion picture|theatrical motion picture|best picture", "Best Picture"),
]


NOISE_RE = re.compile(r"^(ratings?|contents?|external links|see also|references|notes|current awards.*|retired awards|ceremonies|miscellaneous|"
                      r"honorary.*|multiple nominations.*|multiple wins.*|presenters?|performers?|hosts?|preshow.*|produced by|production|"
                      r"summary of.*|most .*|films? with .*)$", re.I)
TV_RE = re.compile(r"television|\btv\b|series|miniseries|streaming|podcast|stand-up", re.I)


def oscar_category(label):
    low = label.lower()
    for pat, cat in OSCAR_RULES:
        if re.search(pat, low):
            return cat
    return None


def norm(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    s = re.sub(r"^(the|a|an) ", "", s.strip())
    return re.sub(r"\s+", " ", s).strip()


class _Page(HTMLParser):
    """Walk Wikipedia's rendered HTML. A 'header' (th, h3/h4, or a block that is only bold)
    names the category; each following <li> is an entry. Bold entries are winners; <i> text is a film."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.cats = []
        self.cur = None
        self.stack = []          # open tags
        self.bold = 0
        self.ital = 0
        self.lis = []            # stack of open <li> frames (winners hold their nominees in a nested list)
        self.hdr = None
        self.skip = 0

    def _flush_header(self):
        if self.hdr is not None:
            text = re.sub(r"\s+", " ", "".join(self.hdr["text"])).strip()
            if text and len(text) < 120 and not re.match(r"^(nominees?|winners?|references?|notes?)$", text, re.I):
                self.cur = {"label": text, "entries": []}
                self.cats.append(self.cur)
            self.hdr = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        cls = a.get("class", "") or ""
        if tag in ("style", "script", "sup") or "reference" in cls or "mw-editsection" in cls:
            self.skip += 1
            self.stack.append((tag, True))
            return
        self.stack.append((tag, False))
        if tag in ("th", "h2", "h3", "h4"):
            self._flush_header()
            self.hdr = {"tag": tag, "text": [], "depth": len(self.stack)}
        elif tag in ("div", "p") and not self.lis:
            self._flush_header()
            self.hdr = {"tag": tag, "text": [], "depth": len(self.stack), "boldonly": True, "other": False}
        if tag in ("b", "strong"):
            self.bold += 1
        if tag in ("i", "em"):
            self.ital += 1
        if tag == "li":
            self._flush_header()
            frame = {"text": [], "bold_chars": 0, "chars": 0, "ital": [], "slot": None}
            if self.cur is not None:
                frame["slot"] = {"text": "", "films": [], "winner": False}
                self.cur["entries"].append(frame["slot"])   # reserve the slot now so order is document order
            self.lis.append(frame)
        if tag == "ul" and not self.lis:
            self._flush_header()

    def handle_endtag(self, tag):
        # pop to matching tag
        while self.stack:
            t, sk = self.stack.pop()
            if sk:
                self.skip -= 1
            if t == tag:
                break
        if tag in ("b", "strong"):
            self.bold = max(0, self.bold - 1)
        if tag in ("i", "em"):
            self.ital = max(0, self.ital - 1)
        if tag in ("th", "h2", "h3", "h4", "div", "p") and self.hdr is not None and self.hdr["tag"] == tag:
            h = self.hdr
            if tag in ("div", "p") and h.get("other"):
                self.hdr = None  # mixed content, not a header
            else:
                self._flush_header()
        if tag == "li" and self.lis:
            li = self.lis.pop()
            text = re.sub(r"\s+", " ", "".join(li["text"])).strip()
            slot = li["slot"]
            if slot is not None:
                winner = li["chars"] > 0 and li["bold_chars"] / li["chars"] > 0.5 or "‡" in text
                slot["text"] = text.replace("‡", "").strip()
                slot["films"] = [re.sub(r"\s+", " ", f).strip() for f in li["ital"] if f.strip()]
                slot["winner"] = bool(winner)

    def handle_data(self, data):
        if self.skip:
            return
        if self.lis:
            li = self.lis[-1]
            li["text"].append(data)
            n = len(data.strip())
            li["chars"] += n
            if self.bold:
                li["bold_chars"] += n
            if self.ital:
                li["ital"].append(data)
        elif self.hdr is not None:
            if data.strip():
                if self.hdr.get("boldonly") and not self.bold:
                    self.hdr["other"] = True
                self.hdr["text"].append(data)


def parse_wikipedia(html):
    """Return [{label, oscar, entries:[{text, films, winner}]}] from a rendered awards page."""
    p = _Page()
    p.feed(html)
    out = []
    for c in p.cats:
        c["entries"] = [e for e in c["entries"] if e["text"]]
        if not c["entries"] or TV_RE.search(c["label"]) or NOISE_RE.match(c["label"]):
            continue
        if len(c["entries"]) < 2:      # tributes/honorees: nobody beat anybody, so nobody "won"
            for e in c["entries"]:
                e["winner"] = False
        out.append({"label": c["label"], "oscar": oscar_category(c["label"]), "entries": c["entries"]})
    return out


def _get(url, tries=4):
    delay = 5
    for i in range(tries):
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Encoding": "identity"})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                body = r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            if e.code in (429, 503) and i < tries - 1:
                time.sleep(int(e.headers.get("Retry-After", delay)) if str(e.headers.get("Retry-After", "")).isdigit() else delay)
                delay *= 2
                continue
            raise
        if body.startswith("You are making too many requests") and i < tries - 1:
            time.sleep(delay)
            delay *= 2
            continue
        return body
    raise RuntimeError("rate limited")


def fetch_wikipedia(title):
    """Return (html, canonical_title) or None when the page does not exist / is only a redirect stub."""
    q = urllib.parse.urlencode({"action": "parse", "page": title, "redirects": 1, "prop": "text",
                                "format": "json", "formatversion": 2, "maxlag": 5})
    try:
        d = json.loads(_get(API + "?" + q))
    except json.JSONDecodeError:
        raise RuntimeError("non-JSON response (rate limited?)")
    if "error" in d:
        return None
    p = d["parse"]
    return p["text"], p["title"]


def match_films(categories, registry):
    """Attach film_id to entries by comparing italic film titles (or the entry text) with registry names."""
    by_name = {norm(f["name"]): fid for fid, f in registry.items()}
    for c in categories:
        for e in c["entries"]:
            e["film_id"] = None
            cands = e["films"] or [e["text"]]
            for cand in cands:
                fid = by_name.get(norm(cand))
                if fid:
                    e["film_id"] = fid
                    break
            else:
                # entry text like "Film Title – Person" without italics
                head = re.split(r"\s+[–—-]\s+", e["text"])[0]
                e["film_id"] = by_name.get(norm(head))
    return categories


def season_guard(categories):
    """A page for last year's ceremony must not be shown as this year's: need at least one tracked film."""
    n = sum(len(c["entries"]) for c in categories)
    hits = sum(1 for c in categories for e in c["entries"] if e.get("film_id"))
    return n < 5 or hits >= 1


def status_of(categories):
    if not categories:
        return "pending"
    return "winners" if any(e["winner"] for c in categories for e in c["entries"]) else "nominees"


def build_event(ev, registry, fetch=fetch_wikipedia):
    """Resolve one event to its record. Raises on network trouble so the caller can keep stale data."""
    for title in ev["titles"]:
        got = fetch(title)
        if not got:
            continue
        html, canon = got
        cats = match_films(parse_wikipedia(html), registry)
        if not cats or not season_guard(cats):
            continue
        return {"id": ev["id"], "name": ev["name"], "short": ev["short"], "order": ev["order"], "status": status_of(cats),
                "source": "wikipedia", "page": canon, "url": "https://en.wikipedia.org/wiki/" + urllib.parse.quote(canon.replace(" ", "_")),
                "categories": cats, "stale": False}
        time.sleep(1.5)
    parser = OFFICIAL_PARSERS.get(ev.get("official") or "")
    if parser:
        cats = match_films(parser(ev), registry)
        if cats and season_guard(cats):
            return {"id": ev["id"], "name": ev["name"], "short": ev["short"], "order": ev["order"], "status": status_of(cats),
                    "source": "official", "page": None, "url": None, "categories": cats, "stale": False}
    return {"id": ev["id"], "name": ev["name"], "short": ev["short"], "order": ev["order"], "status": "pending",
            "source": None, "page": None, "url": None, "categories": [], "stale": False}


def build_by_film(events):
    out = {}
    for ev in events:
        for c in ev["categories"]:
            for e in c["entries"]:
                if e.get("film_id"):
                    out.setdefault(e["film_id"], []).append(
                        {"event": ev["id"], "category": c["label"], "oscar": c["oscar"], "winner": e["winner"]})
    return out


def run(fetch=fetch_wikipedia, events_path=EVENTS, films_path=FILMS, out_path=OUT):
    cfg = json.loads(Path(events_path).read_text())["events"]
    registry = json.loads(Path(films_path).read_text())["films"]
    old = {}
    if Path(out_path).exists():
        old = {e["id"]: e for e in json.loads(Path(out_path).read_text()).get("events", [])}
    events = []
    for ev in cfg:
        try:
            rec = build_event(ev, registry, fetch)
        except Exception as exc:  # network trouble: keep what we had
            print("precursors: %s failed (%s)" % (ev["id"], exc), file=sys.stderr)
            rec = old.get(ev["id"]) or {"id": ev["id"], "name": ev["name"], "short": ev["short"], "order": ev["order"],
                                         "status": "pending", "source": None, "page": None, "url": None, "categories": []}
            rec["stale"] = ev["id"] in old
        events.append(rec)
        time.sleep(1.5)
    doc = {"updated": time.strftime("%Y-%m-%d", time.gmtime()), "events": events, "by_film": build_by_film(events)}
    Path(out_path).write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n")
    return doc


if __name__ == "__main__":
    d = run()
    for e in d["events"]:
        print("%-8s %-9s %2d categories%s" % (e["id"], e["status"], len(e["categories"]), "  (stale)" if e.get("stale") else ""))
