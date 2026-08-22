import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_evidence_manifest import artifact_entry, build_manifest, sha256_file


class EvidenceManifestTests(unittest.TestCase):
    def test_file_entry_contains_hash_and_size(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "report.json"
            path.write_text('{"ok":true}\n', encoding="utf-8")
            entry = artifact_entry(f"basic={path}")
            self.assertTrue(entry["exists"])
            self.assertEqual(entry["sha256"], sha256_file(path))
            self.assertGreater(entry["bytes"], 0)

    def test_manifest_carries_source_context_and_run_provenance(self):
        with tempfile.TemporaryDirectory() as td, patch.dict(os.environ, {"GITHUB_RUN_ID": "123", "GITHUB_SHA": "abc"}, clear=False):
            path = Path(td) / "basic.json"
            path.write_text('{}', encoding="utf-8")
            manifest = build_manifest("SEO Audit", "https://example.com/", [f"basic={path}"], "req-1", "2.6.10-test")
        self.assertEqual(manifest["request"]["source_set_version"], "2.6.10-test")
        self.assertEqual(manifest["github"]["run_id"], "123")
        self.assertEqual(manifest["artifacts"][0]["id"], "basic")

    def test_missing_artifact_is_explicit(self):
        entry = artifact_entry("missing=/tmp/does-not-exist-seo-evidence")
        self.assertFalse(entry["exists"])
        self.assertEqual(entry["type"], "missing")


if __name__ == "__main__":
    unittest.main()
