import unittest
from parse_variety import parse_text


class ParseTests(unittest.TestCase):
    def test_parses_categories_and_people(self):
        s = parse_text("# Picture\n1. Film A\n2. Film B\n# Actor\n1. Film A - X Y, Z\n", "2026-11-08")
        self.assertEqual(s["categories"]["Picture"][1]["film"], "Film B")
        self.assertEqual(s["categories"]["Actor"][0]["people"], ["X Y", "Z"])

    def test_rejects_garbage(self):
        with self.assertRaises(ValueError):
            parse_text("# Picture\nnot a ranked line\n", "2026-11-08")


if __name__ == "__main__":
    unittest.main()
