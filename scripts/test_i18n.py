"""English and Polish UI strings must stay in step: same keys, same placeholders."""
import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

I18N = Path(__file__).resolve().parent.parent / "docs" / "i18n.js"


def load():
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("node not installed")
    code = "global.window={};require(process.argv[1]);process.stdout.write(JSON.stringify(window.I18N))"
    return json.loads(subprocess.run([node, "-e", code, str(I18N)], capture_output=True, text=True, check=True).stdout)


class I18nTests(unittest.TestCase):
    def setUp(self):
        self.d = load()

    def test_same_keys(self):
        en, pl = set(self.d["en"]), set(self.d["pl"])
        self.assertEqual(en - pl, set(), "missing in Polish")
        self.assertEqual(pl - en, set(), "missing in English")

    def test_same_placeholders(self):
        for k, v in self.d["en"].items():
            self.assertEqual(sorted(re.findall(r"\{\w+\}", v)), sorted(re.findall(r"\{\w+\}", self.d["pl"][k])), k)

    def test_plural_keys_complete(self):
        for lang in ("en", "pl"):
            for k in self.d[lang]:
                if k.endswith(".one"):
                    base = k[:-4]
                    self.assertIn(base + ".few", self.d[lang])
                    self.assertIn(base + ".many", self.d[lang])

    def test_polish_is_actually_translated(self):
        same = [k for k, v in self.d["pl"].items() if v == self.d["en"][k] and len(v) > 25]
        self.assertEqual(same, [], "long strings left in English")

    def test_every_category_has_a_label(self):
        data = json.loads((I18N.parent / "data" / "latest.json").read_text())
        for cat in data["categories"]:
            self.assertIn("cat." + cat, self.d["en"])
            self.assertIn("cat." + cat, self.d["pl"])


if __name__ == "__main__":
    unittest.main()
