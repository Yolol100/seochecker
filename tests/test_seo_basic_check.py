import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from seo_basic_check import analyze_html


class AnalyzeHtmlTests(unittest.TestCase):
    def test_extracts_core_seo_fields(self):
        html = """<!doctype html><html><head>
        <title>Voorbeeld pagina</title>
        <meta name="description" content="Een heldere omschrijving.">
        <link rel="canonical" href="/voorbeeld/">
        <script type="application/ld+json">{"@context":"https://schema.org","@type":"Organization"}</script>
        </head><body><h1>Voorbeeld</h1></body></html>"""
        data = analyze_html(html, "https://example.com/test")
        self.assertEqual(data["title"], "Voorbeeld pagina")
        self.assertEqual(data["canonical"], ["https://example.com/voorbeeld/"])
        self.assertEqual(data["h1"], ["Voorbeeld"])
        self.assertEqual(data["jsonld_types"], ["Organization"])
        self.assertEqual(data["indexability_blockers"], [])

    def test_flags_noindex_and_invalid_jsonld(self):
        html = """<html><head><meta name="robots" content="noindex,follow">
        <script type="application/ld+json">{invalid}</script></head><body></body></html>"""
        data = analyze_html(html, "https://example.com/")
        self.assertTrue(data["indexability_blockers"])
        self.assertTrue(data["jsonld_errors"])
        self.assertIn("title ontbreekt", data["warnings"])
        self.assertIn("H1 ontbreekt", data["warnings"])


if __name__ == "__main__":
    unittest.main()
