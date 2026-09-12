import hashlib, json, tempfile, unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from scripts import extract_sitemap_urls as sm, fetch_html_snapshot as snap, safe_http, siteone_resolve, siteone_scope, technical_evidence as te, validate_baseline as vb, verify_page_expectations as exp

class H(dict):
    def get_all(self,k):
        v=self.get(k); return [] if v is None else [v]

class ClosureHardeningTests(unittest.TestCase):
    def test_safe_expectation_fetch(self):
        r=SimpleNamespace(status=200,url='https://example.com/f',connected_ip='93.184.216.34',headers=H({'Content-Type':'text/html'}),body='<title>X</title><h1>Y</h1>')
        with patch('scripts.verify_page_expectations.fetch_text',return_value=r): out=exp.fetch_page('https://example.com/')
        self.assertEqual(out['connected_ip'],'93.184.216.34')
    def test_private_dns_rejected(self):
        with patch('scripts.safe_http.socket.getaddrinfo',return_value=[(2,1,6,'',('127.0.0.1',443))]):
            with self.assertRaises(ValueError): safe_http.resolve_public_ips('https://example.com/')
    def test_siteone_preflight_validates_public_dns_without_forced_ip(self):
        with patch('scripts.siteone_resolve.resolve_public_ips',return_value=['93.184.216.34']) as resolver:
            args=siteone_resolve.build_resolves(['https://example.com/a'],False)
        self.assertEqual(args,[])
        resolver.assert_called_once_with('https://example.com:443/')
    def test_siteone_preflight_writes_explicit_json_evidence(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); urls=root/'urls.txt'; out=root/'preflight.json'; urls.write_text('https://example.com/\n',encoding='utf-8')
            with patch('scripts.siteone_resolve.resolve_public_ips',return_value=['93.184.216.34']), patch('sys.argv',['x','--url-list',str(urls),'--output',str(out)]):
                self.assertEqual(siteone_resolve.main(),0)
            payload=json.loads(out.read_text(encoding='utf-8'))
        self.assertEqual(payload['validated_origin_count'],1)
        self.assertFalse(payload['forced_ip_arguments_emitted'])
        self.assertEqual(payload['network_mode'],'siteone_native_dns_tls')
        self.assertEqual(payload['origins'][0]['public_ips'],['93.184.216.34'])
    def test_sitemap_dtd_rejected(self):
        with self.assertRaises(ValueError): sm.parse_locs(b'<!DOCTYPE x [<!ENTITY y "z">]><urlset/>')
    def test_sitewide_keeps_errors_and_unions_render(self):
        a={'options':{'maxVisitedUrls':10},'stats':{'totalUrls':2},'results':[{'type':1,'url':'https://example.com/a','status':'404'}]}
        b={'options':{'maxVisitedUrls':10},'stats':{'totalUrls':2},'results':[{'type':1,'url':'https://example.com/b','status':'200'}]}
        urls,rep=siteone_scope.extract_page_urls_many([a,b],['https://example.com/'],10)
        self.assertEqual(rep['discovered_error_status_count'],1); self.assertIn('https://example.com/a',urls); self.assertIn('https://example.com/b',urls)
    def test_rendered_coverage_fail_closed(self):
        out=siteone_scope.normalize_rendered({'results':[{'type':1,'url':'https://example.com/a','status':'200','extras':{}}]},['https://example.com/a','https://example.com/b'])
        self.assertFalse(out['coverage']['coverage_complete']); self.assertIn('https://example.com/b',out['coverage']['missing_requested_urls'])
    def test_graph_regression(self):
        self.assertTrue(te.diff_graphs({'issues':[]},{'issues':[{'type':'x','url':'https://example.com/','severity':'warning'}]})['has_regressions'])
        self.assertFalse(te.diff_graphs({'issues':[]},{'issues':[{'type':'x','url':'https://example.com/','severity':'info'}]})['has_regressions'])
    def _baseline_fixture(self, root, findings_schema='1.3', graph_schema='1.3', manifest_schema='1.2'):
        u=root/'u'; f=root/'f'; g=root/'g'
        u.write_text('https://example.com/\n')
        f.write_text(json.dumps({'schema_version':findings_schema,'records':[]})+'\n')
        g.write_text(json.dumps({'schema_version':graph_schema,'issues':[]})+'\n')
        h=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
        m={'schema_version':manifest_schema,'repository':'Yolol100/seochecker','workflow':'SEO Audit','target_url':'https://example.com/','scope':{'crawl_scope':'bounded','runtime_url_fingerprint_sha256':vb.runtime_fingerprint(str(u))},'github':{'run_id':'1','sha':'abc'},'artifacts':[{'id':'technical-findings','type':'file','sha256':h(f)},{'id':'technical-graph','type':'file','sha256':h(g)}]}
        meta={'databaseId':1,'name':'SEO Audit','status':'completed','conclusion':'success','headSha':'abc'}
        return u,f,g,m,meta
    def test_baseline_hash_bound(self):
        with tempfile.TemporaryDirectory() as d:
            u,f,g,m,meta=self._baseline_fixture(Path(d))
            self.assertTrue(vb.validate(m,'https://example.com/','bounded',str(u),500,baseline_run_id='1',run_metadata=meta,findings_path=str(f),graph_path=str(g))['compatible'])
            g.write_text('x')
            self.assertFalse(vb.validate(m,'https://example.com/','bounded',str(u),500,baseline_run_id='1',run_metadata=meta,findings_path=str(f),graph_path=str(g))['compatible'])
    def test_baseline_schema_must_be_supported(self):
        with tempfile.TemporaryDirectory() as d:
            u,f,g,m,meta=self._baseline_fixture(Path(d),findings_schema='1.2')
            result=vb.validate(m,'https://example.com/','bounded',str(u),500,baseline_run_id='1',run_metadata=meta,findings_path=str(f),graph_path=str(g))
            self.assertFalse(result['compatible'])
            self.assertIn('baseline technical-findings schema unsupported: 1.2',result['errors'])
        with tempfile.TemporaryDirectory() as d:
            u,f,g,m,meta=self._baseline_fixture(Path(d),manifest_schema='1.1')
            result=vb.validate(m,'https://example.com/','bounded',str(u),500,baseline_run_id='1',run_metadata=meta,findings_path=str(f),graph_path=str(g))
            self.assertFalse(result['compatible'])
            self.assertIn('baseline manifest schema unsupported: 1.1',result['errors'])
    def test_workflow_and_contract(self):
        root=Path(__file__).resolve().parents[1]; w=(root/'.github/workflows/seo-audit.yml').read_text(); c=json.loads((root/'toolkit-contract.json').read_text());
        for x in ['resolve_audit_request.py','siteone_resolve.py','Validate SiteOne trusted target DNS','reports/siteone-network-preflight.json','--single-page','--before-graph','--run-metadata','fetch_html_snapshot.py','reports/target-snapshot.html','Lighthouse CI collection on trusted target','rendered_normalize.outcome','scope_complete','repos/validator/validator/releases/tags/latest','browser_download_url','vnu-tool-metadata.json','github_release_digest_matched']: self.assertIn(x,w)
        self.assertNotIn('releases/assets/${VNU_ASSET_ID}',w)
        self.assertNotIn('RESOLVE_ARGS',w)
        self.assertNotIn('siteone-resolve-args.txt',w)
        preflight=(root/'scripts/siteone_resolve.py').read_text()
        self.assertIn('intentionally emits no forced-IP arguments',preflight)
        self.assertNotIn('args.append(f"--resolve=',preflight)
        self.assertIn('sitewide scope requires trusted_render_target=true',(root/'scripts/resolve_audit_request.py').read_text()); self.assertNotIn('slice(0, 500)',w); ids={t['id'] for t in c['tools']}; covered=set()
        for a in c['usage_assertions']:
            self.assertIn(a['contains'],(root/a['path']).read_text(),a['tool']); covered.add(a['tool'])
        self.assertEqual(ids,covered)
        nu=next(t for t in c['tools'] if t['id']=='nu-html-checker'); self.assertEqual(nu['version'],'official-latest-digest-verified'); self.assertIn('reports/vnu-tool-metadata.json',nu['outputs'])
        manifest=next(t for t in c['tools'] if t['id']=='evidence-manifest'); self.assertEqual(manifest['version'],'1.2')
    def test_snapshot_local_only(self):
        r=SimpleNamespace(status=200,url='https://example.com/f',connected_ip='93.184.216.34',headers=H({'Content-Type':'text/html'}),body=b'<html/>')
        with tempfile.TemporaryDirectory() as d, patch('scripts.fetch_html_snapshot.fetch_bytes',return_value=r), patch('sys.argv',['x','https://example.com/','--output',d+'/x.html','--metadata',d+'/x.json']): self.assertEqual(snap.main(),0)

if __name__=='__main__': unittest.main()
