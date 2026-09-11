import json, tempfile, unittest
from pathlib import Path
from scripts.resolve_audit_request import resolve

class ResolveAuditRequestTests(unittest.TestCase):
    def base(self):
        return {"enabled":True,"request_id":"audit-001","owner":"seo","project_id":"project-seo","for":"closure","task":"audit","why":"proof","trigger_when":"runtime push","do_not_trigger_when":"untrusted","requested_by":"user","url":"https://example.com/","urls":[],"crawl_scope":"bounded","sitewide_max_urls":500,"render_js":False,"trusted_render_target":False,"baseline_run_id":"","fail_on_regression":True,"source_context":{"project_id":"project-seo","source_set_version":"2.6.29-pagination-clean-url-validation"}}
    def run_req(self, req):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"r.json"; p.write_text(json.dumps(req)); return resolve("push",{},str(p))
    def test_bounded_untrusted_is_allowed(self): self.assertEqual(self.run_req(self.base())["run"],"true")
    def test_render_requires_trust(self):
        r=self.base(); r["render_js"]=True
        with self.assertRaisesRegex(ValueError,"trusted_render_target"): self.run_req(r)
    def test_sitewide_requires_trust(self):
        r=self.base(); r["crawl_scope"]="sitewide"
        with self.assertRaisesRegex(ValueError,"sitewide scope requires"): self.run_req(r)
    def test_more_than_500_urls_fails(self):
        r=self.base(); r["urls"]=[f"https://example.com/{i}" for i in range(500)]
        with self.assertRaisesRegex(ValueError,"hard cap 500"): self.run_req(r)
    def test_baseline_must_be_numeric(self):
        r=self.base(); r["baseline_run_id"]="abc"
        with self.assertRaisesRegex(ValueError,"numeric"): self.run_req(r)
if __name__ == "__main__": unittest.main()
