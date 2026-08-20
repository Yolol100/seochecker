import sys
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from ahrefs_report import api_get, is_suspicious_anchor, summarize_anchors, summarize_history, summarize_refdomains


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return self.payload


class AhrefsSummaryTests(unittest.TestCase):
    def test_detects_spammy_anchor_language(self):
        self.assertTrue(is_suspicious_anchor("High Quality Dofollow Backlinks PBN Rank First Page Google"))
        self.assertFalse(is_suspicious_anchor("Example Brand"))

    def test_summarizes_history(self):
        summary = summarize_history([
            {"date": "2026-05-01", "refdomains": 10},
            {"date": "2026-05-02", "refdomains": 15},
            {"date": "2026-05-03", "refdomains": 14},
        ])
        self.assertEqual(summary["growth"], 4)
        self.assertEqual(summary["largest_daily_increase"]["increase"], 5)

    def test_summarizes_samples(self):
        anchors = [
            {"anchor": "Buy Backlinks", "refdomains": 20, "dofollow_links": 5, "is_spam": True},
            {"anchor": "Example Brand", "refdomains": 2, "dofollow_links": 2, "is_spam": False},
        ]
        self.assertEqual(summarize_anchors(anchors)["suspicious_refdomains_sum"], 20)
        refs = [{"domain": "a.test", "is_spam": True, "traffic_domain": 0}, {"domain": "b.test", "is_spam": False, "traffic_domain": 5}]
        self.assertEqual(summarize_refdomains(refs)["ahrefs_spam_sample_pct"], 50.0)

    def test_retries_http_429_then_succeeds(self):
        error = HTTPError("https://api.ahrefs.com", 429, "Too Many Requests", {"Retry-After": "0"}, BytesIO(b'{"error":"rate"}'))
        delays = []
        with patch("ahrefs_report.urlopen", side_effect=[error, FakeResponse(b'{"metrics":{"live":1}}')]) as mocked:
            result = api_get("backlinks-stats", "secret", {"target": "example.com"}, attempts=2, sleeper=delays.append)
        self.assertEqual(result, {"metrics": {"live": 1}})
        self.assertEqual(mocked.call_count, 2)
        self.assertEqual(delays, [0.0])


if __name__ == "__main__":
    unittest.main()
