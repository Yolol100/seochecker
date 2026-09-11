# SEO Checker — Technical SEO Evidence

SEO Checker turns public website targets into repeatable technical SEO evidence. Project SEO owns strategy and interpretation; this repository owns controlled technical observation, scope metadata and regression evidence. Ahrefs and GSC remain separate evidence sources.

## Evidence chain

`Ahrefs/GSC/SEO-selected scope -> SEO Checker -> normalized findings/relations -> fix -> compatible baseline comparison -> evidence manifest`

The default branch never stores client truth, GSC/Ahrefs exports, target inventories or run evidence.

## Two safety levels

**Safe bounded core** works on a maximum of 500 explicit public URLs. Repository-owned HTTP follows every redirect through `scripts/safe_http.py`: all DNS answers must be globally routable and each TCP connection is pinned to a validated IP while Host/SNI keeps the original hostname.

The safe core also evaluates `robots.txt` as a separate Googlebot **crawlability** evidence layer. It supports Googlebot-specific versus wildcard groups, `Allow`/`Disallow`, longest-match specificity, `*` wildcards and terminal `$` anchors. A robots block is never rewritten into a `noindex` claim: crawl permission and indexability remain separate evidence classes. Current Google fetch semantics are explicit: `2xx` responses are parsed, `4xx` responses except `429` mean no crawl restrictions, while `429`, `5xx` and network/fetch failures remain temporarily unknown because Google may rely on previously cached robots state. The resulting state is carried into `reports/technical-findings.json`, relationship checks in `reports/technical-graph.json`, and before/after regression classification.

**Trusted advanced audit** is enabled only with `trusted_render_target=true`. It may add SiteOne, SiteOne browser rendering and Lighthouse. Before SiteOne runs, `scripts/siteone_resolve.py` verifies that every requested origin resolves only to public addresses and records the result in `reports/siteone-network-preflight.json`. SiteOne then uses its native DNS/TLS stack: its 2.5.1 `--resolve` implementation is deliberately not used for HTTPS because it substitutes the URL hostname with the raw IP and can break TLS/SNI on otherwise healthy sites. Browser/crawler evidence therefore remains restricted to explicitly trusted targets.

## Crawl scopes

`bounded` is the default. It verifies exactly the supplied runtime URL set. SiteOne, when enabled for a trusted target, uses `--url-list` plus `--single-page` and cannot silently expand the page scope.

`sitewide` requires a trusted target. SiteOne discovers pages with an explicit `sitewide_max_urls` cap. Plain and rendered discoveries are unioned before the detailed HTTP parser runs. Error-status pages remain in the effective set. A site-wide completeness claim is valid only when `reports/crawl-scope.json` says `scope_complete: true`.

## Rendered DOM

Set `render_js=true` only when JavaScript can change SEO-relevant output. `reports/rendered-technical-findings.json` is a separate `rendered_dom` layer. Missing requested rendered URLs fail closed. SiteOne JSON does not reliably expose every rendered head relation; decision-critical non-exported signals still require dedicated browser/DOM evidence.

## Regression comparison

A later run can set `baseline_run_id=<earlier successful SEO Audit run>`. The workflow verifies repository, workflow, target, runtime scope, baseline run ID/status/commit and SHA-256 hashes for `technical-findings.json` and `technical-graph.json`. Only then is `reports/regression-diff.json` generated. URL regressions — including newly blocked Googlebot crawlability — and new warning/error relationship issues can fail the run; informational graph observations do not automatically count as regressions.

## Sitemap and markup safety

Sitemap fetches use the pinned HTTP layer, compressed/raw and decompressed byte limits, URL/sitemap count caps, and reject DTD/ENTITY declarations. No advertised sitemap candidates is reported as `not_applicable`; applicable extraction is `complete` only when it finishes without errors or truncation. Sitemap extraction problems are evidence about the target; they do not masquerade as checker execution failures.

Nu HTML Checker never fetches the target directly. `scripts/fetch_html_snapshot.py` first creates a safely fetched local HTML snapshot; Nu validates that local file. The workflow resolves the current official `validator/validator` `latest` release at run time, requires exactly one `vnu.jar`, verifies the downloaded bytes against the SHA-256 digest published in GitHub release metadata, and stores the exact release ID, asset ID, source commit and digest in `reports/vnu-tool-metadata.json`. This avoids stale rolling-release asset IDs without weakening integrity verification.

## Reproducible runtimes

Python-using GitHub Actions jobs are explicitly pinned to Python 3.14.7 through an immutable `actions/setup-python` v7.0.0 commit. Node tooling is lockfile-installed and Lighthouse CI is fixed at 0.15.1. The Nu runtime uses Java 17 through immutable `actions/setup-java` v6.0.1. Checkout and upload actions are also pinned to immutable commit SHAs. Dependabot watches npm and GitHub Actions weekly.

## Evidence manifest

`reports/evidence-manifest.json` uses schema 1.2. It records request/source provenance, run/commit identity, artifact hashes, runtime URL fingerprint and generic scope fields including `scope_complete`, `crawl_limit_reached` and `effective_url_count`. Sitewide legacy aliases remain only for backward compatibility.

Every literal `reports/*` audit artifact is toolkit-contract-owned and, except for the manifest itself, included in the manifest hashing path before upload. Redundant SiteOne text reports are deliberately disabled so uploaded report files cannot bypass provenance.

## Main artifacts

Read `reports/evidence-manifest.json` first. Relevant layers include:

- `reports/basic-seo.json`
- `reports/crawl-scope.json`
- `reports/siteone-network-preflight.json`
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

A green audit does not prove ranking, traffic, conversions or future indexation. Lighthouse is lab data, not CrUX field data. A robots.txt block proves crawler access restriction for the evaluated user agent; it does not by itself prove that Google has or has not indexed a URL.

## Post-publication expectations

`scripts/verify_page_expectations.py` checks non-empty typed runtime expectations using the same pinned safe HTTP layer. URL equality preserves scheme, host including `www`, non-default port, exact path and query. Keep target-specific expectation files off `main`.

## Tests

```bash
python3 -m unittest discover -s tests -v
python3 -m py_compile scripts/*.py tests/*.py
```

## License

This repository currently has no open-source license. Reuse or distribution requires explicit permission from the rights holder.
