import re
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from gsc_report import inspect_url


class GscNeutralDefaultsTests(unittest.TestCase):
    def test_url_inspection_omits_language_when_not_supplied(self):
        with patch("gsc_report.request_json", return_value={}) as request:
            inspect_url("token", "sc-domain:example.com", "https://example.com/", "")
        payload = request.call_args.kwargs["payload"]
        self.assertNotIn("languageCode", payload)

    def test_url_inspection_keeps_explicit_language(self):
        with patch("gsc_report.request_json", return_value={}) as request:
            inspect_url("token", "sc-domain:example.com", "https://example.com/", "nl-NL")
        self.assertEqual(request.call_args.kwargs["payload"]["languageCode"], "nl-NL")

    def test_full_diagnostic_has_no_implicit_market_or_language(self):
        text = (ROOT / ".github" / "workflows" / "full-seo-diagnostic.yml").read_text(encoding="utf-8")
        for key in ("expected_lang", "country_code", "language_code"):
            match = re.search(rf"^      {key}:.*?^        default: \"([^\"]*)\"", text, re.M | re.S)
            self.assertIsNotNone(match, key)
            self.assertEqual(match.group(1), "", key)
        self.assertNotIn('default: "DEU"', text)
        self.assertNotIn('default: "de-DE"', text)


if __name__ == "__main__":
    unittest.main()
