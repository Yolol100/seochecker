import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from seo_basic_check import _parse_robots, analyze_html, fetch, robots_crawlability, robots_fetch_interpretation


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


class RobotsCrawlabilityTests(unittest.TestCase):
    def test_googlebot_specific_group_overrides_wildcard_group(self):
        policy = _parse_robots("""
        User-agent: *
        Disallow: /

        User-agent: Googlebot
        Allow: /
        """)
        decision = robots_crawlability(policy, "https://example.com/private")
        self.assertTrue(decision["allowed"])
        self.assertEqual(decision["matched_rule"], {"directive": "allow", "pattern": "/"})

    def test_longest_rule_wins_and_allow_wins_equal_specificity(self):
        policy = _parse_robots("""
        User-agent: Googlebot
        Disallow: /private/
        Allow: /private/public/
        Disallow: /same
        Allow: /same
        """)
        self.assertTrue(robots_crawlability(policy, "https://example.com/private/public/page")["allowed"])
        self.assertFalse(robots_crawlability(policy, "https://example.com/private/secret")["allowed"])
        self.assertTrue(robots_crawlability(policy, "https://example.com/same")["allowed"])

    def test_wildcard_and_end_anchor_are_supported(self):
        policy = _parse_robots("""
        User-agent: *
        Disallow: /*?print=1$
        """)
        self.assertFalse(robots_crawlability(policy, "https://example.com/page?print=1")["allowed"])
        self.assertTrue(robots_crawlability(policy, "https://example.com/page?print=1&x=2")["allowed"])

    def test_empty_disallow_means_allow_all(self):
        policy = _parse_robots("User-agent: *\nDisallow:\n")
        self.assertTrue(robots_crawlability(policy, "https://example.com/anything")["allowed"])

    def test_google_treats_4xx_except_429_as_no_restrictions(self):
        for status in (400, 401, 403, 404, 410, 451):
            with self.subTest(status=status):
                result = robots_fetch_interpretation(status)
                self.assertEqual(result["state"], "no_valid_robots_file")
                self.assertTrue(result["default_allowed"])

    def test_google_treats_429_and_5xx_as_temporarily_unavailable(self):
        for status in (429, 500, 503, None):
            with self.subTest(status=status):
                result = robots_fetch_interpretation(status)
                self.assertEqual(result["state"], "temporarily_unavailable")
                self.assertIsNone(result["default_allowed"])

    def test_all_2xx_are_processed_as_rules(self):
        for status in (200, 204, 206):
            with self.subTest(status=status):
                self.assertEqual(robots_fetch_interpretation(status)["state"], "rules_available")


class PublicTargetSafetyTests(unittest.TestCase):
    def test_fetch_validates_initial_target_before_network_access(self):
        with patch("seo_basic_check.validate_target", side_effect=ValueError("unsafe target")) as validate:
            with self.assertRaisesRegex(ValueError, "unsafe target"):
                fetch("http://127.0.0.1/")
        validate.assert_called_once_with("http://127.0.0.1/")


if __name__ == "__main__":
    unittest.main()
