import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from seo_basic_check import _x_robots_has_noindex, analyze_html


class ModernSeoRulesTests(unittest.TestCase):
    def test_character_counts_and_multiple_h1_are_measurements_not_google_limits(self):
        html = f"""<html><head><title>{'T' * 100}</title>
        <meta name='description' content='{'D' * 250}'>
        <link rel='canonical' href='https://example.com/'></head>
        <body><h1>Eerste</h1><h1>Tweede</h1></body></html>"""
        data = analyze_html(html, "https://example.com/")
        self.assertEqual(data["title_length"], 100)
        self.assertEqual(data["meta_description_lengths"], [250])
        self.assertEqual(data["h1_count"], 2)
        self.assertNotIn("title is langer dan 65 tekens", data["warnings"])
        self.assertNotIn("meta description is langer dan 160 tekens", data["warnings"])
        self.assertNotIn("meerdere H1's gevonden", data["warnings"])

    def test_x_robots_tag_noindex_respects_googlebot_scope(self):
        self.assertTrue(_x_robots_has_noindex(["noindex, nofollow"]))
        self.assertTrue(_x_robots_has_noindex(["googlebot: noindex"]))
        self.assertFalse(_x_robots_has_noindex(["otherbot: noindex"]))

    def test_hreflang_script_region_and_self_reference(self):
        html = """<html><head><title>Talen</title><meta name='description' content='Beschrijving'>
        <link rel='canonical' href='https://example.com/zh/'>
        <link rel='alternate' hreflang='zh-Hans-US' href='https://example.com/zh/'>
        <link rel='alternate' hreflang='en-US' href='https://example.com/en/'>
        </head><body><h1>Talen</h1></body></html>"""
        data = analyze_html(html, "https://example.com/zh/")
        self.assertEqual(data["hreflang_invalid_languages"], [])
        self.assertTrue(data["hreflang_self_reference"])


if __name__ == "__main__":
    unittest.main()
