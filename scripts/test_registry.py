import unittest
from registry import build, slug


def snap(d, items):
    cats = {}
    for cat, film, win in items:
        cats.setdefault(cat, []).append({"film": film, "studio": "S", "people": ["P"], "winner": win})
    return {"date": d, "categories": cats}


class RegistryTests(unittest.TestCase):
    def test_slug(self):
        self.assertEqual(slug("Dune: Part Three"), "dune-part-three")
        self.assertEqual(slug("Amélie!"), "amelie")

    def test_dropped_film_is_kept_inactive(self):
        r = build([snap("2026-11-01", [("Best Picture", "A", True), ("Best Picture", "B", False)]),
                   snap("2026-11-08", [("Best Picture", "A", False)])])["films"]
        self.assertTrue(r["a"]["active"])
        self.assertFalse(r["b"]["active"])
        self.assertEqual(r["b"]["last_seen"], "2026-11-01")
        self.assertTrue(r["a"]["categories"]["Best Picture"]["ever_winner"])
        self.assertFalse(r["a"]["categories"]["Best Picture"]["winner"])

    def test_two_entries_same_film_and_category_keep_winner_and_count(self):
        r = build([snap("2026-11-08", [("Supporting Actress", "A", True), ("Supporting Actress", "A", False)])])["films"]["a"]["categories"]["Supporting Actress"]
        self.assertTrue(r["winner"])
        self.assertEqual(r["entries"], 2)

    def test_winner_reflects_latest_snapshot_only(self):
        r = build([snap("2026-11-01", [("Directing", "A", True)]),
                   snap("2026-11-08", [("Directing", "A", False), ("Directing", "A", False)])])["films"]["a"]["categories"]["Directing"]
        self.assertFalse(r["winner"])
        self.assertTrue(r["ever_winner"])
        self.assertEqual(r["entries"], 2)

    def test_dropped_category_kept(self):
        r = build([snap("2026-11-01", [("Directing", "A", False), ("Sound", "A", False)]),
                   snap("2026-11-08", [("Sound", "A", False)])])["films"]["a"]["categories"]
        self.assertFalse(r["Directing"]["active"])
        self.assertTrue(r["Sound"]["active"])

    def test_official_marks_nominated_even_if_dropped(self):
        snaps = [snap("2026-11-01", [("Best Picture", "B", False)]),
                 snap("2026-11-08", [("Best Picture", "A", False)])]
        off = [snap("2027-01-21", [("Best Picture", "B", False)])]
        r = build(snaps, off)["films"]
        self.assertEqual(r["b"]["nominated"], ["Best Picture"])
        self.assertFalse(r["b"]["active"])
        self.assertTrue(r["b"]["categories"]["Best Picture"]["official"])
        self.assertEqual(r["a"]["nominated"], [])

    def test_existing_registry_entries_survive_missing_snapshots(self):
        existing = build([snap("2026-11-01", [("Best Picture", "Gone", False)])])
        r = build([snap("2026-11-08", [("Best Picture", "A", False)])], existing=existing)["films"]
        self.assertIn("gone", r)
        self.assertFalse(r["gone"]["active"])


if __name__ == "__main__":
    unittest.main()
