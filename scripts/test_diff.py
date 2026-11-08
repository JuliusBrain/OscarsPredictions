import unittest
from diff import diff, pick_baseline


def snap(d, entries):
    return {"date": d, "categories": {"Best Picture": [
        {"film": f, "studio": "S", "people": [], "winner": w} for f, w in entries]}}


class DiffTests(unittest.TestCase):
    def test_new_winner_changes_and_dropped(self):
        old = snap("2026-11-01", [("A", True), ("B", False), ("C", False)])
        new = snap("2026-11-08", [("A", False), ("B", True), ("D", False)])
        r = diff(new, old)
        self.assertEqual(r["entries"]["Best Picture|A"], "winner_lost")
        self.assertEqual(r["entries"]["Best Picture|B"], "winner_gained")
        self.assertEqual(r["entries"]["Best Picture|D"], "new")
        self.assertEqual([d["film"] for d in r["dropped"]], ["C"])

    def test_unchanged(self):
        s = snap("2026-11-01", [("A", True)])
        t = snap("2026-11-08", [("A", True)])
        self.assertEqual(diff(t, s)["entries"]["Best Picture|A"], "same")

    def test_baseline_is_newest_at_least_seven_days_old(self):
        snaps = [snap(d, []) for d in ("2026-11-01", "2026-11-05", "2026-11-09", "2026-11-12")]
        self.assertEqual(pick_baseline(snaps, snaps[-1])["date"], "2026-11-05")

    def test_baseline_falls_back_to_earliest(self):
        snaps = [snap("2026-11-10", []), snap("2026-11-12", [])]
        self.assertEqual(pick_baseline(snaps, snaps[-1])["date"], "2026-11-10")

    def test_no_baseline(self):
        s = snap("2026-11-12", [("A", False)])
        self.assertIsNone(pick_baseline([s], s))
        self.assertEqual(diff(s, None)["entries"], {})


if __name__ == "__main__":
    unittest.main()
