# SEO Checker — Technical SEO Evidence

SEO Checker turns public website targets into repeatable technical SEO evidence. **Project SEO owns strategy and interpretation; this repository owns controlled technical observation, scope metadata and regression evidence.** Ahrefs and GSC remain separate evidence sources.

## Evidence chain

`Ahrefs/GSC/SEO-selected scope -> SEO Checker -> normalized findings/relations -> fix -> compatible baseline comparison -> evidence manifest`

The repository never stores client truth, Ahrefs/GSC exports or run-specific target inventories on `main`.

## Crawl scopes

### `bounded` (default)
Use for URLs selected by GSC, Ahrefs, sitemap evidence or the SEO Skill. Maximum 500 runtime URLs. SiteOne receives `--url-list` **and** `--single-page`, so discovered page links are not silently expanded.

### `sitewide`
Use only when a whole-site technical crawl is required. SiteOne discovers same-scope HTML pages with an explicit `sitewide_max_urls` cap. The discovered page set is then passed through the repository's detailed HTTP parser, so canonical, hreflang, pagination and sitemap relations are normalized consistently.

A site-wide completeness claim is valid only when `reports/crawl-scope.json` says `scope_complete: true`. Hitting the crawl cap fails the critical evidence gate instead of silently claiming full coverage.

## Rendered DOM

Set `render_js=true` only when JavaScript can change SEO-relevant output. Browser mode is fail-closed unless `trusted_render_target=true`, because a real browser may load page subresources outside the crawler's top-document scope.

Rendered output remains separate: `reports/siteone-rendered.json`, `reports/siteone-rendered.html`, and `reports/rendered-technical-findings.json`.

SiteOne 2.5.1 JSON does not reliably expose every rendered head relation. The normalized rendered artifact publishes an explicit coverage boundary. If rendered hreflang, pagination or another non-exported DOM signal can change acceptance, use dedicated browser/DOM evidence; never silently substitute HTTP-response HTML.

## Automatic regression comparison

Pass `baseline_run_id=<earlier SEO Audit run id>` to a later run. The workflow downloads the previous `seo-audit-report`, verifies repository, workflow, target and runtime scope compatibility, and only then creates `reports/baseline-validation.json` and `reports/regression-diff.json`. With `fail_on_regression=true`, regressions or missing-after URLs fail the audit gate.

## Technical coverage

Within the explicit observed scope the checker covers HTTP/final URL state, robots/X-Robots-Tag, title/description/H1, canonical targets/loops/chains/cross-domain targets, hreflang target health/return links/canonical consistency, `rel=next`/`rel=prev` consistency, sitemap redirects/non-200/noindex/canonical mismatches, SiteOne diagnostics, Lighthouse CI lab evidence, local Nu HTML validation, post-publication expectations, and before/after regression comparison.

Technical tool findings are diagnostics, not Google ranking or indexing verdicts.

## Network safety

Repository-owned HTTP and sitemap requests use `scripts/safe_http.py`: every request/redirect hop is DNS-resolved, all resolved addresses must be globally routable, and the TCP connection is pinned to a validated IP while preserving original Host/SNI. URL credentials are rejected. Sitemap responses have both compressed/raw and decompressed size bounds.

Third-party SiteOne browser mode cannot provide the same per-subresource pinning guarantee, so rendered mode requires an explicit trusted-target acknowledgement.

## Main artifacts

Read `reports/evidence-manifest.json` first. Then use `reports/crawl-scope.json`, `reports/technical-findings.json`, `reports/technical-graph.json`, `reports/rendered-technical-findings.json`, `reports/regression-diff.json`, `reports/lighthouse-summary.json`, and `reports/w3c-nu.json` as their separate evidence layers.

## External evidence boundaries

- **GSC**: Google's owned Search performance and URL Inspection/index evidence.
- **Ahrefs**: Ahrefs' keyword, backlink, market and competitive datasets.
- **SEO Checker**: current reproducible technical observation and regression evidence.
- **SEO Skill / Project SEO sources**: interpretation, prioritization and acceptance requirements.

Do not add GSC OAuth, Ahrefs API keys, keyword databases or backlink databases to this repository.

## Local tests

```bash
python3 -m unittest discover -s tests -v
python3 -m py_compile scripts/*.py tests/*.py
```

## Post-publication expectations

`scripts/verify_page_expectations.py` checks explicitly supplied runtime expectations. Keep client/URL-specific expectation files off `main`.

## License

This repository currently has no open-source license. Reuse or distribution requires explicit permission from the rights holder.
