import json
import tempfile
import unittest
from pathlib import Path

import precursors as P

FIX = Path(__file__).parent / "fixtures" / "wiki_awards.html"
REG = {"hamnet": {"name": "Hamnet"}, "marty-supreme": {"name": "Marty Supreme"}}


class Parse(unittest.TestCase):
    def setUp(self):
        self.cats = P.match_films(P.parse_wikipedia(FIX.read_text()), REG)
        self.by = {c["label"]: c for c in self.cats}

    def test_categories_and_oscar_mapping(self):
        self.assertEqual([c["label"] for c in self.cats],
                         ["Best Motion Picture – Drama", "Best Director", "Best Actress in a Leading Role", "Best Supporting Actress",
                          "Best Motion Picture – Musical or Comedy"])
        self.assertEqual([c["oscar"] for c in self.cats], ["Best Picture", "Directing", "Actress", "Supporting Actress", "Best Picture"])

    def test_nested_winner_layout_as_on_real_pages(self):
        e = self.by["Best Motion Picture – Musical or Comedy"]["entries"]
        self.assertEqual([(x["text"], x["winner"]) for x in e], [("Marty Supreme", True), ("Hamnet", False), ("Other Film", False)])

    def test_winner_is_the_bold_entry(self):
        drama = self.by["Best Motion Picture – Drama"]["entries"]
        self.assertEqual([e["winner"] for e in drama], [True, False, False])
        self.assertEqual(drama[0]["text"], "Hamnet")

    def test_reference_markers_are_ignored(self):
        self.assertEqual(self.by["Best Motion Picture – Drama"]["entries"][2]["text"], "Some Unknown Film")

    def test_film_matching_uses_italics_not_person_names(self):
        d = self.by["Best Director"]["entries"]
        self.assertEqual([e["film_id"] for e in d], ["hamnet", "marty-supreme"])
        self.assertIsNone(self.by["Best Supporting Actress"]["entries"][1]["film_id"])

    def test_references_section_is_not_a_category(self):
        self.assertNotIn("References", self.by)


class Logic(unittest.TestCase):
    def test_oscar_category_order(self):
        self.assertEqual(P.oscar_category("Best Supporting Actor – Motion Picture"), "Supporting Actor")
        self.assertEqual(P.oscar_category("Best Original Screenplay"), "Original Screenplay")
        self.assertEqual(P.oscar_category("Best Actor in a Leading Role"), "Actor")
        self.assertIsNone(P.oscar_category("Best Costume Design"))
        self.assertEqual(P.oscar_category("Best Supporting Male Actor in a Motion Picture"), "Supporting Actor")
        self.assertEqual(P.oscar_category("Best Supporting Female Actor in a Motion Picture"), "Supporting Actress")
        self.assertEqual(P.oscar_category("Best Female Actor in a Motion Picture – Drama"), "Actress")

    def test_television_categories_are_dropped(self):
        html = "<div><b>Best Actor in a Television Series</b></div><ul><li><b>A – <i>X</i></b></li></ul>"
        self.assertEqual(P.parse_wikipedia(html), [])

    def test_navigation_and_noise_sections_are_dropped(self):
        html = "<h2>External links</h2><ul><li>A</li><li>B</li></ul><h3>Best Picture</h3><ul><li><b><i>X</i></b></li></ul>"
        self.assertEqual([c["label"] for c in P.parse_wikipedia(html)], ["Best Picture"])

    def test_single_entry_tributes_are_not_winners(self):
        html = "<h3>Director Tribute</h3><ul><li><b>Danny Boyle – <i>Ink</i></b></li></ul>"
        cats = P.parse_wikipedia(html)
        self.assertFalse(cats[0]["entries"][0]["winner"])

    def test_status(self):
        self.assertEqual(P.status_of([]), "pending")
        self.assertEqual(P.status_of([{"entries": [{"winner": False}]}]), "nominees")
        self.assertEqual(P.status_of([{"entries": [{"winner": True}]}]), "winners")

    def test_season_guard_rejects_old_ceremony(self):
        old = [{"entries": [{"film_id": None} for _ in range(6)]}]
        self.assertFalse(P.season_guard(old))
        self.assertTrue(P.season_guard([{"entries": [{"film_id": "x"}] + [{"film_id": None}] * 5}]))

    def test_run_keeps_stale_data_and_handles_missing_pages(self):
        ev = {"events": [
            {"id": "a", "name": "A", "short": "A", "order": 1, "titles": ["T1"]},
            {"id": "b", "name": "B", "short": "B", "order": 2, "titles": ["Missing"]},
            {"id": "c", "name": "C", "short": "C", "order": 3, "titles": ["Boom"]}]}
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / "e.json").write_text(json.dumps(ev))
            (d / "f.json").write_text(json.dumps({"films": REG}))
            prev = {"events": [{"id": "c", "name": "C", "short": "C", "order": 3, "status": "nominees", "categories": [], "source": "wikipedia"}]}
            (d / "o.json").write_text(json.dumps(prev))

            def fetch(title):
                if title == "T1":
                    return FIX.read_text(), "Page One"
                if title == "Boom":
                    raise RuntimeError("rate limited")
                return None
            P.time.sleep = lambda s: None
            doc = P.run(fetch, d / "e.json", d / "f.json", d / "o.json")
        st = {e["id"]: e for e in doc["events"]}
        self.assertEqual(st["a"]["status"], "winners")
        self.assertEqual(st["a"]["url"], "https://en.wikipedia.org/wiki/Page_One")
        self.assertEqual(st["b"]["status"], "pending")
        self.assertTrue(st["c"]["stale"])
        self.assertEqual(st["c"]["status"], "nominees")
        hn = doc["by_film"]["hamnet"]
        self.assertTrue(any(x["event"] == "a" and x["oscar"] == "Directing" and x["winner"] for x in hn))


if __name__ == "__main__":
    unittest.main()
