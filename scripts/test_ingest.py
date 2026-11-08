import tempfile
import unittest
from pathlib import Path

from ingest_variety import ingest, summarize, unmapped_films
from test_parse import page


def html(winner="A"):
    films = {"A": "&#8220;A&#8221; (Neon)", "B": "&#8220;B&#8221; (A24)"}
    lines = [films[k] + (" ***" if k == winner else "") for k in ("A", "B")]
    return page(("Best Picture", lines), ("Directing", ["Jo Doe", "&#8220;A&#8221; (Neon)"]))


class IngestTests(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())

    def run_ingest(self, text, day):
        return ingest(text, day, self.d, min_categories=1)

    def test_first_run_writes_snapshot(self):
        r = self.run_ingest(html(), "2026-11-08")
        self.assertEqual(r["status"], "new")
        self.assertTrue((self.d / "2026-11-08.json").exists())

    def test_identical_page_writes_nothing(self):
        self.run_ingest(html(), "2026-11-08")
        r = self.run_ingest(html(), "2026-11-09")
        self.assertEqual(r["status"], "unchanged")
        self.assertFalse((self.d / "2026-11-09.json").exists())

    def test_changed_winner_is_reported(self):
        self.run_ingest(html("A"), "2026-11-08")
        r = self.run_ingest(html("B"), "2026-11-09")
        self.assertEqual(r["status"], "new")
        text = "\n".join(r["lines"])
        self.assertIn("WINNER: B is now the predicted winner in Best Picture", text)
        self.assertIn("NOT WINNER: A is no longer the predicted winner in Best Picture", text)

    def test_new_and_dropped_entries(self):
        old = {"categories": {"Best Picture": [{"film": "A", "winner": False}, {"film": "B", "winner": False}]}}
        new = {"categories": {"Best Picture": [{"film": "A", "winner": False}, {"film": "C", "winner": True}]}}
        lines = summarize(old, new)
        self.assertIn("NEW: C in Best Picture (predicted winner)", lines)
        self.assertIn("DROPPED: B from Best Picture", lines)

    def test_unmapped_films(self):
        snap = {"categories": {"Best Picture": [{"film": "Dune: Part Three"}, {"film": "Brand New"}]}}
        self.assertEqual(unmapped_films(snap, {"dune-part-three": "https://x"}), ["Brand New"])
        self.assertEqual(unmapped_films(snap, {"dune-part-three": None, "brand-new": "u"}), ["Dune: Part Three"])

    def test_block_page_is_rejected(self):
        with self.assertRaises(ValueError):
            ingest("<html>402 Payment Required</html>", "2026-11-08", self.d)
        with self.assertRaises(ValueError):  # too few categories for the real page
            ingest(html(), "2026-11-08", self.d)


if __name__ == "__main__":
    unittest.main()
