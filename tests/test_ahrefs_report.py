import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from ahrefs_report import is_suspicious_anchor, summarize_anchors, summarize_history, summarize_refdomains


class AhrefsSummaryTests(unittest.TestCase):
    def test_detects_spammy_anchor_language(self):
        self.assertTrue(is_suspicious_anchor("High Quality Dofollow Backlinks PBN Rank First Page Google"))
        self.assertFalse(is_suspicious_anchor("Doctor Cura"))

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
            {"anchor": "Doctor Cura", "refdomains": 2, "dofollow_links": 2, "is_spam": False},
        ]
        self.assertEqual(summarize_anchors(anchors)["suspicious_refdomains_sum"], 20)
        refs = [{"domain": "a.test", "is_spam": True, "traffic_domain": 0}, {"domain": "b.test", "is_spam": False, "traffic_domain": 5}]
        self.assertEqual(summarize_refdomains(refs)["ahrefs_spam_sample_pct"], 50.0)


if __name__ == "__main__":
    unittest.main()
