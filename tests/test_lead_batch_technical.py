"""No-network fixtures for free, private specialist SEO evidence."""
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from lead_batch_technical import HEADERS, inspect_site, store_private_evidence


class TechnicalLeadProbeTests(unittest.TestCase):
    def test_robots_block_and_failed_source_do_not_become_sales_claims(self):
        def fetch(url, **kwargs):
            return SimpleNamespace(status=200, body="User-agent: *\nDisallow: /", url=url)
        status, details = inspect_site("https://example.invalid/", fetch=fetch, analyze=lambda *args: {})
        self.assertEqual((status, details["reason"]), ("NOT_RUN", "robots_disallowed"))
        def bad_fetch(*args, **kwargs):
            raise OSError("private host name must never go to logs")
        status, details = inspect_site("https://example.invalid/", fetch=bad_fetch, analyze=lambda *args: {})
        self.assertEqual(status, "NIET_VERIFIEERBAAR")
        self.assertNotIn("private host", str(details))

    def test_valid_html_emits_limited_technical_facts_without_paid_api(self):
        def fetch(url, **kwargs):
            if url.endswith("robots.txt"):
                return SimpleNamespace(status=404, body="", url=url)
            return SimpleNamespace(status=200, body="<html></html>", url=url,
                headers={"Content-Type":"text/html"}, truncated=False)
        def analyze(html, url):
            return {"title":"Example", "meta_descriptions":[], "h1_count":1,
                    "canonical":[url], "jsonld_types":[], "warnings":["meta description ontbreekt"],
                    "indexability_blockers":[]}
        status, facts = inspect_site("https://example.invalid/", fetch=fetch, analyze=analyze)
        self.assertEqual(status, "BEVESTIGD")
        self.assertEqual(facts["ahrefs_paid_api_units"], 0)
        self.assertEqual(facts["sales_opportunity"], "NIET_BEWEZEN")
        self.assertEqual(facts["rendered_ux"], "NOT_RUN")

    def test_private_append_and_readback_no_rewrites(self):
        state={"values":[]}
        conn=Mock()
        def get(url, **kw):
            resp=Mock(status_code=200)
            if "?fields=" in url:
                resp.json.return_value={"sheets":[{"properties":{"title":"OpportunityAudits","sheetId":1}}]}
            else:
                resp.json.return_value={"values":state["values"]}
            return resp
        def post(url, **kw):
            request=kw["json"]["requests"]
            for op in request:
                if "updateCells" in op:
                    state["values"]=[list(HEADERS)]
                if "appendCells" in op:
                    for row in op["appendCells"]["rows"]:
                        state["values"].append([cell["userEnteredValue"]["stringValue"] for cell in row["values"]])
            return Mock(status_code=200)
        conn.get.side_effect=get
        conn.post.side_effect=post
        row=["12", "Approved:abc", "hash", "seo-technical-v1", "2026-11-22T00:00:00Z", "BEVESTIGD", "{}"]
        self.assertEqual(store_private_evidence(conn,"https://sheets.googleapis.com/v4/spreadsheets/test",[row]),1)
        self.assertEqual(store_private_evidence(conn,"https://sheets.googleapis.com/v4/spreadsheets/test",[row]),0)
        self.assertEqual(state["values"],[list(HEADERS),row])

if __name__=="__main__":
    unittest.main()
