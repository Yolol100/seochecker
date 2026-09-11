import unittest

from scripts.technical_evidence import diff_runs, normalize_payload, url_key, validate_graph


class TechnicalEvidenceTests(unittest.TestCase):
    def test_url_key_preserves_resource_identity(self):
        self.assertEqual(url_key("HTTPS://Example.COM:443/path?q=1#x"), "https://example.com/path?q=1")
        self.assertNotEqual(url_key("https://www.example.com/path"), url_key("https://example.com/path"))

    def test_self_canonical_is_not_a_loop(self):
        normalized = normalize_payload({"records": [
            {"requested_url": "https://example.com/a", "http": {"status": 200, "final_url": "https://example.com/a"}, "canonical": ["https://example.com/a"]},
        ]})
        graph = validate_graph(normalized)
        self.assertNotIn("canonical_loop", {x["type"] for x in graph["issues"]})

    def test_real_canonical_cycle_is_reported(self):
        normalized = normalize_payload({"records": [
            {"requested_url": "https://example.com/a", "http": {"status": 200, "final_url": "https://example.com/a"}, "canonical": ["https://example.com/b"]},
            {"requested_url": "https://example.com/b", "http": {"status": 200, "final_url": "https://example.com/b"}, "canonical": ["https://example.com/a"]},
        ]})
        graph = validate_graph(normalized)
        self.assertIn("canonical_loop", {x["type"] for x in graph["issues"]})

    def test_normalize_and_graph_find_hreflang_return_gap(self):
        payload = {"records": [
            {"requested_url": "https://example.com/en", "http": {"status": 200, "final_url": "https://example.com/en"}, "canonical": ["https://example.com/en"], "hreflang": [{"lang": "nl", "url": "https://example.com/nl"}]},
            {"requested_url": "https://example.com/nl", "http": {"status": 200, "final_url": "https://example.com/nl"}, "canonical": ["https://example.com/nl"], "hreflang": []},
        ]}
        normalized = normalize_payload(payload)
        graph = validate_graph(normalized)
        kinds = {x["type"] for x in graph["issues"]}
        self.assertIn("hreflang_return_link_missing", kinds)

    def test_sitemap_reconciliation_respects_bounded_observation_scope(self):
        normalized = normalize_payload({"records": [
            {"requested_url": "https://example.com/a", "http": {"status": 200, "final_url": "https://example.com/a"}, "canonical": ["https://example.com/a"]},
            {"requested_url": "https://example.com/b", "http": {"status": 200, "final_url": "https://example.com/b"}, "canonical": ["https://example.com/b"]},
        ]})
        graph = validate_graph(normalized, ["https://example.com/a", "https://example.com/not-observed"])
        kinds = {x["type"] for x in graph["issues"]}
        self.assertNotIn("sitemap_url_not_observed", kinds)
        self.assertIn("indexable_observed_url_missing_from_sitemap", kinds)
        self.assertEqual(graph["sitemap_url_count"], 2)

    def test_crawlability_stays_separate_from_indexability(self):
        normalized = normalize_payload({"records": [{
            "requested_url": "https://example.com/private",
            "http": {"status": 200, "final_url": "https://example.com/private"},
            "canonical": ["https://example.com/private"],
            "robots_googlebot": {"user_agent": "googlebot", "allowed": False, "matched_rule": {"directive": "disallow", "pattern": "/private"}},
            "crawlability_blockers": ["robots.txt blokkeert Googlebot voor de uiteindelijke URL"],
        }]})
        record = normalized["records"][0]
        self.assertTrue(record["indexable"])
        self.assertFalse(record["crawlable_googlebot"])
        graph = validate_graph(normalized)
        self.assertIn("url_blocked_by_robots_googlebot", {x["type"] for x in graph["issues"]})

    def test_diff_classifies_crawlability_regression(self):
        before = normalize_payload({"records": [{
            "requested_url": "https://example.com/a",
            "http": {"status": 200, "final_url": "https://example.com/a"},
            "robots_googlebot": {"user_agent": "googlebot", "allowed": True, "matched_rule": None},
        }]})
        after = normalize_payload({"records": [{
            "requested_url": "https://example.com/a",
            "http": {"status": 200, "final_url": "https://example.com/a"},
            "robots_googlebot": {"user_agent": "googlebot", "allowed": False, "matched_rule": {"directive": "disallow", "pattern": "/"}},
            "crawlability_blockers": ["robots.txt blokkeert Googlebot voor de uiteindelijke URL"],
        }]})
        diff = diff_runs(before, after)
        self.assertEqual(diff["counts"]["regressed"], 1)
        self.assertTrue(diff["has_regressions"])

    def test_diff_classifies_regression_and_improvement(self):
        before = normalize_payload({"records": [
            {"requested_url": "https://example.com/a", "http": {"status": 500, "final_url": "https://example.com/a"}, "indexability_blockers": ["bad"]},
            {"requested_url": "https://example.com/b", "http": {"status": 200, "final_url": "https://example.com/b"}},
        ]})
        after = normalize_payload({"records": [
            {"requested_url": "https://example.com/a", "http": {"status": 200, "final_url": "https://example.com/a"}},
            {"requested_url": "https://example.com/b", "http": {"status": 500, "final_url": "https://example.com/b"}, "indexability_blockers": ["bad"]},
        ]})
        diff = diff_runs(before, after)
        self.assertEqual(diff["counts"]["improved"], 1)
        self.assertEqual(diff["counts"]["regressed"], 1)


if __name__ == "__main__":
    unittest.main()
