import unittest
from parse_variety import parse_html


def page(*articles):
    out = ""
    for title, lines in articles:
        out += ('<article class="pmc-fallback-list-item"><h2>%s</h2><div class="pmc-not-a-paywall">'
                '<p class="paragraph x text-align-left">%s</p></div></article>' % (title, "<br>".join(lines)))
    return out


class ParseTests(unittest.TestCase):
    def test_film_first_with_winner_and_credits(self):
        h = page(("Best Picture", ["&#8220;<strong>A</strong>&#8221; (Neon) ***", "X Y, Z (p.g.a.)",
                                    "&#8220;<strong>B</strong>&#8221; (A24)", "Q and R"]))
        e = parse_html(h, "2026-11-08")["categories"]["Best Picture"]
        self.assertEqual(e[0], {"film": "A", "studio": "Neon", "people": ["X Y", "Z"], "winner": True})
        self.assertEqual(e[1]["people"], ["Q", "R"])
        self.assertFalse(e[1]["winner"])

    def test_person_first(self):
        h = page(("Actor", ["<strong>Matt Damon</strong>", "&#8220;The Odyssey&#8221; (Universal)",
                            "Andrew Scott ***", "&#8220;Elsinore&#8221; (Focus)"]))
        e = parse_html(h, "d")["categories"]["Actor"]
        self.assertEqual((e[0]["people"], e[0]["film"], e[0]["winner"]), (["Matt Damon"], "The Odyssey", False))
        self.assertTrue(e[1]["winner"])

    def test_song_and_international(self):
        h = page(("Original Song", ["&#8220;Tune&#8221; from &#8220;Movie&#8221; (A24)"]),
                 ("International Feature", ["&#8220;Fjord&#8221; from Romania (Neon)", "Dir. Jo Bloggs"]))
        c = parse_html(h, "d")["categories"]
        self.assertEqual((c["Original Song"][0]["song"], c["Original Song"][0]["film"]), ("Tune", "Movie"))
        self.assertEqual((c["International Feature"][0]["country"], c["International Feature"][0]["people"]),
                         ("Romania", ["Jo Bloggs"]))

    def test_layout_change_is_an_error(self):
        with self.assertRaises(ValueError):
            parse_html("<html></html>", "d")


if __name__ == "__main__":
    unittest.main()
