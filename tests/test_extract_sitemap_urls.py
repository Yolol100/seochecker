import unittest
from unittest.mock import patch

from urllib.request import Request

from scripts.extract_sitemap_urls import PublicOnlyRedirectHandler, parse_locs, sitemap_seeds


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

    def test_redirect_target_is_validated_before_following(self):
        handler = PublicOnlyRedirectHandler()
        req = Request("https://example.com/sitemap.xml")
        with patch("scripts.extract_sitemap_urls.validate_target", side_effect=ValueError("private target")) as validate:
            with self.assertRaisesRegex(ValueError, "private target"):
                handler.redirect_request(req, None, 302, "Found", {}, "http://127.0.0.1/private.xml")
            validate.assert_called_once_with("http://127.0.0.1/private.xml")


if __name__ == "__main__":
    unittest.main()
