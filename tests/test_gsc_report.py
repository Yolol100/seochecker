import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from gsc_report import largest_weekly_impression_drop, period_comparison


class GscSummaryTests(unittest.TestCase):
    def test_period_comparison_detects_drop(self):
        rows = []
        from datetime import date, timedelta
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
        from datetime import date, timedelta
        start = date(2026, 1, 1)
        for i in range(30):
            value = 100 if i < 15 else 10
            rows.append({"keys": [(start + timedelta(days=i)).isoformat()], "impressions": value, "clicks": 0, "ctr": 0, "position": 1})
        result = largest_weekly_impression_drop(rows, "2026-01-01", "2026-01-30")
        self.assertIsNotNone(result)
        self.assertLess(result["change_pct"], 0)


if __name__ == "__main__":
    unittest.main()
