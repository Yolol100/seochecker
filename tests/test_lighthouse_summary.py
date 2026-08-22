import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from lighthouse_summary import build_summary, discover_lhrs


def lhr(performance, lcp, seo=1.0, seo_audit_score=1.0):
    return {
        "requestedUrl": "https://example.com/",
        "finalUrl": "https://example.com/",
        "fetchTime": "2026-08-22T00:00:00.000Z",
        "lighthouseVersion": "13.0.1",
        "categories": {
            "performance": {"score": performance, "auditRefs": []},
            "seo": {"score": seo, "auditRefs": [{"id": "document-title", "weight": 1}]},
        },
        "audits": {
            "largest-contentful-paint": {"numericValue": lcp, "numericUnit": "millisecond", "score": performance},
            "document-title": {"title": "Document has a title", "score": seo_audit_score, "scoreDisplayMode": "binary"},
        },
    }


class LighthouseSummaryTests(unittest.TestCase):
    def test_builds_median_and_failed_seo_audits(self):
        with tempfile.TemporaryDirectory() as td:
            paths = []
            for idx, payload in enumerate([lhr(.8, 2500), lhr(.9, 2000, .9, 0), lhr(.7, 3000)]):
                path = Path(td) / f"lhr-{idx}.json"
                path.write_text(json.dumps(payload), encoding="utf-8")
                paths.append(path)
            summary = build_summary(paths)
        self.assertEqual(summary["run_count"], 3)
        self.assertEqual(summary["median"]["categories"]["performance"], 0.8)
        self.assertEqual(summary["median"]["metrics"]["largest_contentful_paint"]["numeric_value"], 2500.0)
        self.assertEqual(summary["runs"][1]["seo_failures"][0]["id"], "document-title")

    def test_discover_ignores_non_lhr_json(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "lhr.json").write_text(json.dumps(lhr(.8, 2500)), encoding="utf-8")
            (root / "manifest.json").write_text(json.dumps({"foo": "bar"}), encoding="utf-8")
            self.assertEqual([p.name for p in discover_lhrs(root)], ["lhr.json"])


if __name__ == "__main__":
    unittest.main()
