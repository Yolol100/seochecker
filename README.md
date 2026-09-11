# SEO Checker — Technical SEO Evidence

SEO Checker turns public website targets into repeatable technical SEO evidence. Project SEO owns strategy and interpretation; this repository owns controlled technical observation, scope metadata and regression evidence. Ahrefs and GSC remain separate evidence sources.

## Evidence chain

`Ahrefs/GSC/SEO-selected scope -> SEO Checker -> normalized findings/relations -> fix -> compatible baseline comparison -> evidence manifest`

The default branch never stores client truth, GSC/Ahrefs exports, target inventories or run evidence.

## Two safety levels

**Safe bounded core** works on a maximum of 500 explicit public URLs. Repository-owned HTTP follows every redirect through `scripts/safe_http.py`: all DNS answers must be globally routable and each TCP connection is pinned to a validated IP while Host/SNI keeps the original hostname.

**Trusted advanced audit** is enabled only with `trusted_render_target=true`. It may add SiteOne, SiteOne browser rendering and Lighthouse. SiteOne receives explicit `--resolve` mappings for requested hosts. Browser subresources are still an external runtime boundary, so browser/crawler evidence is never enabled for an untrusted arbitrary target.

## Crawl scopes

`bounded` is the default. It verifies exactly the supplied runtime URL set. SiteOne, when enabled for a trusted target, uses `--url-list` plus `--single-page` and cannot silently expand the page scope.

`sitewide` requires a trusted target. SiteOne discovers pages with an explicit `sitewide_max_urls` cap. Plain and rendered discoveries are unioned before the detailed HTTP parser runs. Error-status pages remain in the effective set. A site-wide completeness claim is valid only when `reports/crawl-scope.json` says `scope_complete: true`.

## Rendered DOM

Set `render_js=true` only when JavaScript can change SEO-relevant output. `reports/rendered-technical-findings.json` is a separate `rendered_dom` layer. Missing requested rendered URLs fail closed. SiteOne JSON does not reliably expose every rendered head relation; decision-critical non-exported signals still require dedicated browser/DOM evidence.

## Regression comparison

A later run can set `baseline_run_id=<earlier successful SEO Audit run>`. The workflow verifies repository, workflow, target, runtime scope, baseline run ID/status/commit and SHA-256 hashes for `technical-findings.json` and `technical-graph.json`. Only then is `reports/regression-diff.json` generated. URL regressions and new warning/error relationship issues can fail the run; informational graph observations do not automatically count as regressions.

## Sitemap and markup safety

Sitemap fetches use the pinned HTTP layer, compressed/raw and decompressed byte limits, URL/sitemap count caps, and reject DTD/ENTITY declarations. Sitemap extraction problems are evidence about the target; they do not masquerade as checker execution failures.

Nu HTML Checker never fetches the target directly. `scripts/fetch_html_snapshot.py` first creates a safely fetched local HTML snapshot; Nu validates that local file. The workflow resolves the current official `validator/validator` `latest` release at run time, requires exactly one `vnu.jar`, verifies the downloaded bytes against the SHA-256 digest published in GitHub release metadata, and stores the exact release ID, asset ID, source commit and digest in `reports/vnu-tool-metadata.json`. This avoids stale rolling-release asset IDs without weakening integrity verification.

## Main artifacts

Read `reports/evidence-manifest.json` first. Relevant layers include:

- `reports/basic-seo.json`
- `reports/crawl-scope.json`
- `reports/technical-findings.json`
- `reports/technical-graph.json`
- `reports/rendered-technical-findings.json`
- `reports/sitemap-extraction.json`
- `reports/lighthouse-summary.json`
- `reports/target-snapshot.json`
- `reports/vnu-tool-metadata.json`
- `reports/w3c-nu.json`
- `reports/baseline-validation.json`
- `reports/regression-diff.json`

## Evidence boundaries

GSC is the owned Google Search/index evidence source. Ahrefs owns its market, keyword, backlink and competitive data. SEO Checker owns reproducible technical observations. The SEO Skill and Project SEO sources own interpretation, prioritization and acceptance requirements.

A green audit does not prove ranking, traffic, conversions or future indexation. Lighthouse is lab data, not CrUX field data.

## Post-publication expectations

`scripts/verify_page_expectations.py` checks non-empty typed runtime expectations using the same pinned safe HTTP layer. URL equality preserves scheme, host including `www`, non-default port, exact path and query. Keep target-specific expectation files off `main`.

## Tests

```bash
python3 -m unittest discover -s tests -v
python3 -m py_compile scripts/*.py tests/*.py
```

## License

This repository currently has no open-source license. Reuse or distribution requires explicit permission from the rights holder.
