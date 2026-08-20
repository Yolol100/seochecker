import sys
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

mod = types.ModuleType("seo_basic_check")
mod.analyze_html = lambda html, url: {"hreflang": []}
mod.fetch = lambda url, timeout=25: (200, url, {}, "")
sys.modules.setdefault("seo_basic_check", mod)

from language_probe import extract_html_lang, language_matches


class LanguageProbeTests(unittest.TestCase):
    def test_extract_html_lang(self):
        self.assertEqual(extract_html_lang('<html lang="de-DE"><head></head></html>'), "de-DE")

    def test_language_match(self):
        self.assertTrue(language_matches("de-DE", "de"))
        self.assertFalse(language_matches("en", "de"))
        self.assertFalse(language_matches(None, "de"))


if __name__ == "__main__":
    unittest.main()
