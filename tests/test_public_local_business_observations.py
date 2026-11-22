import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from seo_basic_check import analyze_html


class PublicLocalBusinessEvidenceTests(unittest.TestCase):
    """Public site hints only: no profile or AI rank inference and no HTTP calls."""

    def test_nested_graph_reuses_existing_jsonld_parse_without_contact_values(self):
        html = """<html><head><title>Test</title><meta name="description" content="Test">
        <link rel="canonical" href="https://example.com/">
        <script type="application/ld+json">{
          "@context": "https://schema.org",
          "@graph": [
            {"@type": "WebSite", "url": "https://example.com"},
            {"@type": ["LocalBusiness", "Restaurant"], "name": "Example Diner",
             "url": "https://example.com/", "telephone": "+31 123 456 789",
             "address": {"@type": "PostalAddress", "streetAddress": "Teststraat 1"},
             "openingHoursSpecification": [{"@type": "OpeningHoursSpecification", "opens": "09:00"}],
             "potentialAction": {"@type": "ReserveAction", "target": "https://example.com/boek"}}
          ]}</script></head><body><h1>Diner</h1></body></html>"""
        out = analyze_html(html, "https://example.com/")
        self.assertIn("LocalBusiness", out["jsonld_types"])
        self.assertIn("Restaurant", out["jsonld_types"])
        self.assertEqual(out["jsonld_localbusiness_fields_present"],
                         ["address", "name", "openingHoursSpecification", "potentialAction", "telephone", "url"])
        self.assertNotIn("+31 123", str(out["jsonld_localbusiness_fields_present"]))
        self.assertNotIn("Teststraat", str(out["jsonld_localbusiness_fields_present"]))
        self.assertFalse(out["jsonld_errors"])

    def test_organization_only_is_not_assumed_localbusiness(self):
        html = '<html><script type="application/ld+json">{"@type":"Organization","name":"Example","address":"Some address"}</script></html>'
        out = analyze_html(html, "https://example.com/")
        self.assertEqual(out["jsonld_types"], ["Organization"])
        self.assertEqual(out["jsonld_localbusiness_fields_present"], [])
        self.assertNotIn("geen LocalBusiness", " ".join(out["warnings"]))

    def test_broken_jsonld_does_not_invent_local_evidence(self):
        html = '<script type="application/ld+json">{invalid}</script>'
        out = analyze_html(html, "https://example.com/")
        self.assertEqual(out["jsonld_localbusiness_fields_present"], [])
        self.assertTrue(out["jsonld_errors"])

    def test_empty_fields_and_nontarget_nested_nodes_not_inferred(self):
        html = """<script type="application/ld+json">[
          {"@type":"LocalBusiness", "name":"", "url":"https://example.com/"},
          {"@type":"Organization", "telephone":"123", "sameAs":["https://example.net/"]}
        ]</script>"""
        out = analyze_html(html, "https://example.com/")
        self.assertEqual(out["jsonld_localbusiness_fields_present"], ["url"])
        self.assertEqual(out["jsonld_errors"], [])


if __name__ == "__main__":
    unittest.main()
