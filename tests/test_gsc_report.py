import sys
import unittest
from datetime import date, timedelta
from io import BytesIO
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from gsc_report import largest_weekly_impression_drop, period_comparison, request_json, summarize_sitemaps


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return self.payload


class GscSummaryTests(unittest.TestCase):
    def test_period_comparison_detects_drop(self):
        rows = []
        end = date(2026, 8, 18)
        start = end - timedelta(days=55)
        cursor = start
        while cursor <= end:
            age = (cursor - start).days
            impressions = 100 if age < 28 else 20
            rows.append({"keys": [cursor.isoformat()], "clicks": impressions / 10, "impressions": impressions, "ctr": .1, "position": 10})
            cursor += timedelta(days=1)
        summary = period_comparison(rows, end.isoformat(), 28)
        self.assertEqual(summary["impressions_change_pct"], -80.0)

    def test_largest_weekly_drop_returns_negative_change(self):
        rows = []
        start = date(2026, 1, 1)
        for i in range(30):
            value = 100 if i < 15 else 10
            rows.append({"keys": [(start + timedelta(days=i)).isoformat()], "impressions": value, "clicks": 0, "ctr": 0, "position": 1})
        result = largest_weekly_impression_drop(rows, "2026-01-01", "2026-01-30")
        self.assertIsNotNone(result)
        self.assertLess(result["change_pct"], 0)

    def test_summarizes_submitted_sitemaps(self):
        summary = summarize_sitemaps({
            "sitemap": [
                {"path": "https://example.com/sitemap.xml", "errors": "0", "warnings": "0", "isPending": False},
                {"path": "https://example.com/products.xml", "errors": "2", "warnings": "1", "isPending": True},
            ]
        })
        self.assertEqual(summary["submitted_count"], 2)
        self.assertEqual(summary["with_errors_or_warnings_count"], 1)
        self.assertEqual(summary["pending_count"], 1)
        self.assertEqual(summary["problematic"][0]["path"], "https://example.com/products.xml")

    def test_retries_http_429_then_succeeds(self):
        error = HTTPError("https://example.test", 429, "Too Many Requests", {"Retry-After": "0"}, BytesIO(b'{"error":"rate"}'))
        delays = []
        with patch("gsc_report.urlopen", side_effect=[error, FakeResponse(b'{"ok": true}')]) as mocked:
            result = request_json("https://example.test", attempts=2, sleeper=delays.append)
        self.assertEqual(result, {"ok": True})
        self.assertEqual(mocked.call_count, 2)
        self.assertEqual(delays, [0.0])


if __name__ == "__main__":
    unittest.main()
