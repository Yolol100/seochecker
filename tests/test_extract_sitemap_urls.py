import unittest

from scripts.extract_sitemap_urls import build_report, parse_locs, sitemap_seeds


class SitemapExtractionTests(unittest.TestCase):
    def test_parse_urlset_and_index(self):
        kind, urls = parse_locs(b'<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>https://example.com/a</loc></url></urlset>')
        self.assertEqual(kind, "urlset")
        self.assertEqual(urls, ["https://example.com/a"])
        kind, urls = parse_locs(b'<?xml version="1.0"?><sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><sitemap><loc>https://example.com/sitemap-2.xml</loc></sitemap></sitemapindex>')
        self.assertEqual(kind, "sitemapindex")
        self.assertEqual(urls, ["https://example.com/sitemap-2.xml"])

    def test_sitemap_seeds_are_deduplicated(self):
        payload = {"records": [
            {"sitemap_candidates": ["https://example.com/sitemap.xml"]},
            {"sitemap_candidates": ["https://example.com/sitemap.xml", "https://example.com/news.xml"]},
        ]}
        self.assertEqual(sitemap_seeds(payload), ["https://example.com/sitemap.xml", "https://example.com/news.xml"])

    def test_no_candidates_are_explicitly_not_applicable_but_complete(self):
        report = build_report(
            [],
            [],
            [],
            False,
            max_sitemaps=100,
            max_urls=10_000,
            max_bytes=20_000_000,
            max_decompressed_bytes=50_000_000,
        )
        self.assertEqual(report["schema_version"], "1.3")
        self.assertEqual(report["status"], "not_applicable")
        self.assertFalse(report["applicable"])
        self.assertTrue(report["complete"])

    def test_errors_make_applicable_extraction_partial(self):
        report = build_report(
            ["https://example.com/sitemap.xml"],
            [],
            [{"sitemap": "https://example.com/sitemap.xml", "error": "bad xml"}],
            False,
            max_sitemaps=100,
            max_urls=10_000,
            max_bytes=20_000_000,
            max_decompressed_bytes=50_000_000,
        )
        self.assertEqual(report["status"], "partial")
        self.assertTrue(report["applicable"])
        self.assertFalse(report["complete"])


if __name__ == "__main__":
    unittest.main()
