import unittest
from datetime import date
from pathlib import Path
from filmweb import normalize, parse_pl_date, parse_main, parse_dates, poland_cinema, build_record, needs_refresh

FIX = Path(__file__).parent / "fixtures"
MAIN = (FIX / "filmweb_main.html").read_text()
DATES = (FIX / "filmweb_dates.html").read_text()


class FilmwebTests(unittest.TestCase):
    def test_polish_dates(self):
        self.assertEqual(parse_pl_date("20 marca 2026"), "2026-03-20")
        self.assertEqual(parse_pl_date("1 września 2027"), "2027-09-01")
        self.assertIsNone(parse_pl_date("wkrótce"))

    def test_main_page(self):
        m = parse_main(MAIN)
        self.assertEqual((m["world_premiere"], m["pl_cinema_main"]), ("2026-03-09", "2026-03-20"))
        self.assertEqual((m["title_pl"], m["title_original"], m["year"]), ("Projekt Hail Mary", "Project Hail Mary", 2026))

    def test_dates_page_and_poland(self):
        d = parse_dates(DATES)
        self.assertTrue(any(x["country"] == "GB" and x["note"] for x in d))
        self.assertEqual(poland_cinema(d), "2026-03-20")

    def test_record_and_conflict_flag(self):
        r = build_record("u", MAIN, DATES, date(2026, 11, 8))
        self.assertEqual((r["world_premiere"], r["pl_cinema"], r["dates_conflict"]), ("2026-03-09", "2026-03-20", False))
        changed = MAIN.replace('localPremiereDate:  "2026-03-20"', 'localPremiereDate:  "2026-03-18"')
        self.assertTrue(build_record("u", changed, DATES, date(2026, 11, 8))["dates_conflict"])

    def test_normalize_original_title_and_year_only_date(self):
        n = normalize({"title_pl": "Naza", "title_original": None, "world_premiere": "2026", "pl_cinema": "2026-10-23"})
        self.assertEqual(n["title_original"], "Naza")
        self.assertIsNone(n["world_premiere"])
        self.assertEqual(n["world_premiere_year"], 2026)
        self.assertEqual(n["pl_cinema"], "2026-10-23")

    def test_needs_refresh(self):
        today = date(2026, 11, 8)
        self.assertTrue(needs_refresh(None, today))
        self.assertTrue(needs_refresh({"pl_cinema": "2026-12-18", "fetched": "2026-11-08"}, today))   # upcoming
        self.assertFalse(needs_refresh({"pl_cinema": "2026-03-20", "fetched": "2026-11-05"}, today))  # settled, fresh
        self.assertTrue(needs_refresh({"pl_cinema": "2026-03-20", "fetched": "2026-10-20"}, today))   # settled, old
        self.assertTrue(needs_refresh({"pl_cinema": "2026-03-20", "fetched": "2026-11-08", "stale": True}, today))


if __name__ == "__main__":
    unittest.main()
