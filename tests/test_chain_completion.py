import gzip
import socket
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import safe_http
from scripts.build_evidence_manifest import build_manifest
from scripts.extract_sitemap_urls import _bounded_gzip_decompress
from scripts.run_url_batch import load_urls
from scripts.siteone_scope import extract_page_urls, normalize_rendered
from scripts.technical_evidence import diff_runs, normalize_payload, validate_graph
from scripts.validate_baseline import runtime_fingerprint, validate as validate_baseline

ROOT = Path(__file__).resolve().parents[1]


class SafeHttpTests(unittest.TestCase):
    def test_rejects_non_public_dns_answers(self):
        fake=[(socket.AF_INET,socket.SOCK_STREAM,6,"",("127.0.0.1",443))]
        with patch("scripts.safe_http.socket.getaddrinfo", return_value=fake):
            with self.assertRaisesRegex(ValueError,"Niet-publiek"): safe_http.resolve_public_ips("https://example.com/")

    def test_pinned_connection_uses_validated_ip_not_hostname(self):
        with patch("scripts.safe_http.socket.create_connection") as create:
            conn=safe_http._PinnedHTTPConnection("example.com",80,"93.184.216.34",3); conn.connect()
        self.assertEqual(create.call_args.args[0], ("93.184.216.34",80))


class SitemapBoundsTests(unittest.TestCase):
    def test_bounded_gzip_rejects_decompression_bomb(self):
        with self.assertRaisesRegex(ValueError,"max_decompressed_bytes"): _bounded_gzip_decompress(gzip.compress(b"x"*10000),100)


class ScopeAndGraphTests(unittest.TestCase):
    def test_strict_url_list_rejects_over_cap_instead_of_truncating(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/"urls.txt"; path.write_text("".join(f"https://example.com/{i}\n" for i in range(501)),encoding="utf-8")
            with patch("scripts.run_url_batch.validate_target", side_effect=lambda x:x):
                with self.assertRaisesRegex(ValueError,"exceeds max_urls=500"): load_urls(str(path),500)

    def test_canonical_chain_cross_domain_sitemap_redirect_and_pagination(self):
        payload={"records":[
            {"requested_url":"https://example.com/a","http":{"status":200,"final_url":"https://example.com/a"},"canonical":["https://example.com/b"],"pagination_next":["https://example.com/b"]},
            {"requested_url":"https://example.com/b","http":{"status":200,"final_url":"https://example.com/b"},"canonical":["https://example.com/c"],"pagination_prev":[]},
            {"requested_url":"https://example.com/c","http":{"status":200,"final_url":"https://example.com/c"},"canonical":["https://other.example/c"]},
            {"requested_url":"https://example.com/old","http":{"status":200,"final_url":"https://example.com/new"},"canonical":["https://example.com/new"]}
        ]}
        graph=validate_graph(normalize_payload(payload),["https://example.com/old"],scope_complete=True)
        kinds={x["type"] for x in graph["issues"]}
        for kind in ["canonical_chain","canonical_cross_domain","sitemap_url_redirected","pagination_reciprocal_missing"]: self.assertIn(kind,kinds)

    def test_diff_flags_missing_after_as_regression(self):
        before=normalize_payload({"records":[{"requested_url":"https://example.com/a","http":{"status":200,"final_url":"https://example.com/a"}}]}); after=normalize_payload({"records":[]})
        self.assertTrue(diff_runs(before,after)["has_regressions"])

    def test_sitewide_scope_detects_cap(self):
        payload={"options":{"maxVisitedUrls":2},"stats":{"totalUrls":2},"results":[{"url":"https://example.com/a","status":"200 OK","type":1},{"url":"https://example.com/b","status":"200","type":1}]}
        _,report=extract_page_urls(payload,[],10); self.assertTrue(report["crawl_limit_reached"]); self.assertFalse(report["scope_complete"])

    def test_rendered_normalization_publishes_coverage_boundary(self):
        payload={"results":[{"url":"https://example.com/","status":"200 OK","type":1,"extras":{"Title":"T","H1":"H","Canonical":"/","Robots":"index,follow"}}]}
        out=normalize_rendered(payload,["https://example.com/"]); self.assertEqual(out["records"][0]["observation_layer"],"rendered_dom"); self.assertIn("full hreflang set",out["coverage"]["not_exported_reliably_by_siteone_json"])


class BaselineAndContractTests(unittest.TestCase):
    def test_baseline_must_match_target_and_runtime_scope(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/"urls.txt"; path.write_text("https://example.com/a\n",encoding="utf-8"); fp=runtime_fingerprint(str(path))
            manifest={"repository":"Yolol100/seochecker","workflow":"SEO Audit","target_url":"https://example.com/a","scope":{"crawl_scope":"bounded","runtime_url_fingerprint_sha256":fp}}
            self.assertTrue(validate_baseline(manifest,"https://example.com/a","bounded",str(path),500)["compatible"])
            self.assertFalse(validate_baseline(manifest,"https://example.org/a","bounded",str(path),500)["compatible"])

    def test_manifest_records_scope_and_baseline(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"urls.txt"; p.write_text("https://example.com/a\n",encoding="utf-8")
            m=build_manifest("SEO Audit","https://example.com/a",[],"req","2.6.30","bounded",str(p),500,"123","")
        self.assertEqual(m["scope"]["runtime_url_count"],1); self.assertEqual(m["request"]["baseline_run_id"],"123")

    def test_workflow_and_toolkit_have_all_hard_gates(self):
        text=(ROOT/".github/workflows/seo-audit.yml").read_text(encoding="utf-8")
        resolver=(ROOT/"scripts/resolve_audit_request.py").read_text(encoding="utf-8")
        for value in ["--single-page","--max-visited-urls","crawl_scope","trusted_render_target","baseline_run_id","validate_baseline.py","regression-diff.json","rendered-technical-findings.json","resolve_audit_request.py"]: self.assertIn(value,text)
        self.assertIn("runtime URL list exceeds hard cap 500",resolver)
        self.assertNotIn("slice(0, 500)",text)
        import json
        contract=json.loads((ROOT/"toolkit-contract.json").read_text(encoding="utf-8")); self.assertEqual({x["id"] for x in contract["tools"]},{x["tool"] for x in contract["usage_assertions"]})


if __name__ == "__main__": unittest.main()
