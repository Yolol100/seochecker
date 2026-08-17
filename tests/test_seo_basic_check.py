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
        self.assertFalse(data["canonical_self_referencing"])
        self.assertIn("canonical wijst niet naar de uiteindelijke pagina-URL", data["warnings"])
        self.assertEqual(data["h1"], ["Voorbeeld"])
        self.assertEqual(data["jsonld_types"], ["Organization"])
        self.assertEqual(data["indexability_blockers"], [])

    def test_accepts_self_referencing_canonical_after_url_normalization(self):
        html = """<html><head>
        <title>Canonical</title>
        <meta name="description" content="Beschrijving">
        <link rel="canonical" href="https://EXAMPLE.com/pagina#fragment">
        </head><body><h1>Canonical</h1></body></html>"""
        data = analyze_html(html, "https://example.com/pagina")
        self.assertTrue(data["canonical_self_referencing"])
        self.assertNotIn("canonical wijst niet naar de uiteindelijke pagina-URL", data["warnings"])

    def test_extracts_hreflang_and_flags_duplicate_and_invalid_languages(self):
        html = """<html><head>
        <title>Talen</title>
        <meta name="description" content="Beschrijving">
        <link rel="canonical" href="https://example.com/nl/">
        <link rel="alternate" hreflang="nl" href="/nl/">
        <link rel="alternate" hreflang="NL" href="/nl-alt/">
        <link rel="alternate" hreflang="en-GB" href="/en/">
        <link rel="alternate" hreflang="x-default" href="/">
        <link rel="alternate" hreflang="not_a_lang" href="/invalid/">
        </head><body><h1>Talen</h1></body></html>"""
        data = analyze_html(html, "https://example.com/nl/")
        self.assertEqual(data["hreflang_duplicate_languages"], ["nl"])
        self.assertEqual(data["hreflang_invalid_languages"], ["not_a_lang"])
        self.assertIn("dubbele hreflang-taalcodes gevonden", data["warnings"])
        self.assertIn("ongeldige of niet-herkende hreflang-taalcodes gevonden", data["warnings"])
        self.assertEqual(
            data["hreflang"],
            [
                {"lang": "nl", "url": "https://example.com/nl/"},
                {"lang": "nl", "url": "https://example.com/nl-alt/"},
                {"lang": "en-gb", "url": "https://example.com/en/"},
                {"lang": "x-default", "url": "https://example.com/"},
                {"lang": "not_a_lang", "url": "https://example.com/invalid/"},
            ],
        )

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
