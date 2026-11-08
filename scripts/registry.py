"""Film registry: every film ever seen on the list, kept even after it drops.

Built from all snapshots in data/snapshots (never deleted) and merged into the
existing docs/data/films.json, so nothing is lost. Official Academy nominees
(data/official/*.json, same schema as a snapshot) mark films/categories as
nominated.
"""
import re
import unicodedata


def slug(name):
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-")


def _film(name, studio, date):
    return {"id": slug(name), "name": name, "studio": studio, "first_seen": date,
            "last_seen": date, "active": False, "nominated": [], "categories": {}}


def _cat(date):
    return {"first_seen": date, "last_seen": date, "active": False, "winner": False,
            "ever_winner": False, "official": False, "people": []}


def build(snaps, official=None, existing=None):
    snaps = sorted(snaps, key=lambda s: s["date"])
    films = {}
    for snap in snaps:
        for cat, entries in snap["categories"].items():
            for e in entries:
                fid = slug(e["film"])
                f = films.setdefault(fid, _film(e["film"], e["studio"], snap["date"]))
                f["name"], f["studio"], f["last_seen"] = e["film"], e["studio"], snap["date"]
                c = f["categories"].setdefault(cat, _cat(snap["date"]))
                c["last_seen"], c["winner"] = snap["date"], e["winner"]
                c["ever_winner"] = c["ever_winner"] or e["winner"]
                c["people"] = sorted(set(c["people"]) | set(e["people"]))
    latest = snaps[-1]["date"] if snaps else None
    for f in films.values():
        f["active"] = f["last_seen"] == latest
        for c in f["categories"].values():
            c["active"] = c["last_seen"] == latest
            c["winner"] = c["winner"] and c["active"]

    for fid, old in (existing or {}).get("films", {}).items():
        if fid not in films:
            old = dict(old, active=False)
            old["categories"] = {k: dict(v, active=False, winner=False) for k, v in old["categories"].items()}
            films[fid] = old
        else:
            for cat, oc in old["categories"].items():
                films[fid]["categories"].setdefault(cat, dict(oc, active=False, winner=False))
            films[fid]["first_seen"] = min(films[fid]["first_seen"], old["first_seen"])

    if official:
        off = sorted(official, key=lambda s: s["date"])[-1]
        for f in films.values():
            f["nominated"] = []
            for c in f["categories"].values():
                c["official"] = False
        for cat, entries in off["categories"].items():
            for e in entries:
                fid = slug(e["film"])
                f = films.setdefault(fid, _film(e["film"], e["studio"], off["date"]))
                f["active"] = f["active"] or False
                c = f["categories"].setdefault(cat, _cat(None))
                c["official"] = True
                if cat not in f["nominated"]:
                    f["nominated"].append(cat)
        for f in films.values():
            f["nominated"].sort()
    return {"updated": latest, "films": dict(sorted(films.items()))}
