import json
import re
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from scripts import safe_http

ROOT = Path(__file__).resolve().parents[1]


class ExhaustiveContractTests(unittest.TestCase):
    def test_every_report_path_is_contract_owned_and_manifested(self):
        workflow = (ROOT / ".github/workflows/seo-audit.yml").read_text(encoding="utf-8")
        contract = json.loads((ROOT / "toolkit-contract.json").read_text(encoding="utf-8"))

        report_paths = set(re.findall(r"reports/[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*", workflow))
        manifest_paths = set(re.findall(r"--artifact\s+[A-Za-z0-9_.-]+=(reports/[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*)", workflow))
        contract_paths = {
            output.rstrip("/")
            for tool in contract["tools"]
            for output in tool.get("outputs", [])
            if isinstance(output, str) and output.startswith("reports/")
        }

        self.assertEqual(report_paths - contract_paths, set(), "workflow references report paths that the toolkit contract does not own")
        self.assertEqual(
            report_paths - manifest_paths - {"reports/evidence-manifest.json"},
            set(),
            "workflow report artifacts must be hashed in the evidence manifest",
        )
        self.assertNotIn("--output-text-file=", workflow, "redundant SiteOne text reports must not bypass the manifest contract")

    def test_safe_http_revalidates_redirect_target_before_connecting(self):
        raw = SimpleNamespace(
            status=302,
            headers={"Location": "http://127.0.0.1/private"},
            read=lambda _: b"",
        )
        connection = MagicMock()
        connection.getresponse.return_value = raw

        with patch("scripts.safe_http.resolve_public_ips", side_effect=[["93.184.216.34"], ValueError("private redirect")]) as resolver:
            with patch("scripts.safe_http._PinnedHTTPSConnection", return_value=connection):
                with self.assertRaisesRegex(ValueError, "private redirect"):
                    safe_http.fetch_bytes("https://example.com/")

        self.assertEqual(resolver.call_count, 2)


if __name__ == "__main__":
    unittest.main()
