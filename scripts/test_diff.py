import unittest
from diff import diff, pick_baseline


def snap(d, picture):
    return {"date": d, "categories": {"Picture": [
        {"rank": i + 1, "film": f, "people": []} for i, f in enumerate(picture)]}}


class DiffTests(unittest.TestCase):
    def test_moves_new_dropped(self):
        old = snap("2026-11-01", ["A", "B", "C"])
        new = snap("2026-11-08", ["B", "A", "D"])
        r = diff(new, old)["entries"]
        self.assertEqual(r["Picture|B"]["status"], "up")
        self.assertEqual(r["Picture|A"]["status"], "down")
        self.assertEqual(r["Picture|D"]["status"], "new")
        self.assertEqual(diff(new, old)["dropped"][0]["film"], "C")

    def test_baseline_is_newest_at_least_seven_days_old(self):
        snaps = [snap("2026-11-01", ["A"]), snap("2026-11-05", ["A"]),
                 snap("2026-11-09", ["A"]), snap("2026-11-12", ["A"])]
        self.assertEqual(pick_baseline(snaps, snaps[-1])["date"], "2026-11-05")

    def test_baseline_falls_back_to_earliest(self):
        snaps = [snap("2026-11-10", ["A"]), snap("2026-11-12", ["A"])]
        self.assertEqual(pick_baseline(snaps, snaps[-1])["date"], "2026-11-10")

    def test_no_baseline(self):
        s = snap("2026-11-12", ["A"])
        self.assertIsNone(pick_baseline([s], s))
        self.assertEqual(diff(s, None)["entries"], {})


if __name__ == "__main__":
    unittest.main()
