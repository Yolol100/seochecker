import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_diagnostic_report import build_signals


class DiagnosticRulesTests(unittest.TestCase):
    def test_prioritizes_google_index_issue_and_backlink_spam(self):
        basic = {"indexability_blockers": []}
        language = {"status": "ok", "language_matches_expected": True}
        gsc = {
            "status": "ok",
            "url_inspection": {"inspectionResult": {"indexStatusResult": {"verdict": "FAIL"}}},
            "target_country": {"period_comparison": {"impressions_change_pct": -90}},
        }
        ahrefs = {
            "status": "ok",
            "anchor_summary": {"suspicious_refdomains_sum": 210},
            "refdomains_sample_summary": {"ahrefs_spam_sample_pct": 80},
        }
        signals = build_signals(basic, language, gsc, ahrefs)
        kinds = [s["type"] for s in signals]
        self.assertIn("google_index_status", kinds)
        self.assertIn("gsc_visibility_drop", kinds)
        self.assertIn("automated_backlink_spam", kinds)
        self.assertEqual(signals[0]["type"], "google_index_status")


if __name__ == "__main__":
    unittest.main()
