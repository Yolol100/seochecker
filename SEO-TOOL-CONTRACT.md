# SEO Tool Contract: seochecker + Ahrefs

This repository has one job: produce current technical evidence for a public owned URL/site. It does not replace Ahrefs and it does not call Ahrefs directly.

## Roles

### seochecker

Purpose: answer **what is technically true now on this public owned URL/site?**

Use for:

- HTTP/final URL and redirect behavior
- robots/noindex, canonical and sitemap checks
- title, meta description and H1 checks
- JSON-LD syntax/types
- SiteOne technical crawl
- Lighthouse CI lab evidence
- W3C Nu HTML validation
- technical pre/post-change regression evidence

Do not use as a source for keyword demand, competitor opportunity, backlink authority, ranking estimates, Rank Tracker, Brand Radar or Google's indexed/performance state.

### Ahrefs

Purpose: answer **where is the external search, market, competitive, ranking or link opportunity/context?**

Use for:

- Keywords Explorer and SERP context
- organic competitors, estimated rankings and top pages
- backlinks, referring domains and link gaps
- Rank Tracker
- Brand Radar
- existing Ahrefs Site Audit project/report questions

Ahrefs metrics are third-party diagnostic data. An Ahrefs crawl does not replace a current live technical verification when the action depends on current implementation.

## When to use one or both

| Situation | seochecker | Ahrefs |
|---|---:|---:|
| Technical audit or technical regression | yes | only if impact/priority needs market or authority data |
| Keyword, competitor or SERP opportunity | only for selected owned URL readiness | yes |
| Backlink/referring-domain analysis | only to verify an owned target/replacement URL | yes |
| Existing Ahrefs Site Audit report question | optional live verification | yes |
| Migration, pruning, cleanup or redirect priority | yes | yes when ranking/link/value context changes the decision |
| Broken backlink recovery | yes on target/replacement | yes to find and value the link opportunity |
| Complete technical + market/authority audit | yes | yes |

## Order

1. Start from the decision, not the tools.
2. Technical trigger: run seochecker/live checks first, then use Ahrefs only for impact, demand, competition or authority context.
3. Keyword/backlink/competitor trigger: use Ahrefs first, then run seochecker only on owned URLs selected for action.
4. Migration/pruning/cleanup: collect both evidence classes before redirect/noindex/delete/consolidate decisions.
5. Return one normalized SEO decision, not two tool dumps.

## Evidence precedence

- Current HTTP, redirects, directives, canonical, sitemap, markup and live crawl state: current seochecker/direct live evidence wins over an older third-party crawl snapshot.
- Google's indexed state and owned Google Search performance: Search Console is the higher evidence layer.
- Ahrefs keyword, backlink, referring-domain, estimated ranking/traffic, Rank Tracker and Brand Radar metrics: Ahrefs is the source for its own dataset only.
- If technical results disagree, compare run dates and scope and re-check live. Do not average conflicting signals.

## Invocation

- Repository: `Yolol100/seochecker`
- Workflow: `.github/workflows/seo-audit.yml` (`SEO Audit`)
- Input: one explicit public `http://` or `https://` URL
- Output: workflow summary and artifact `seo-audit-report`
- Security: private, loopback, link-local and other non-public targets are rejected

Repository read access does not prove workflow-dispatch capability. The orchestration layer may call this repo only when GitHub Actions dispatch or an equivalent repository runtime is actually executable. Otherwise repo execution is `handoff_required`; Ahrefs must not be used as a silent replacement for missing live technical evidence.

## Return contract for the SEO orchestration layer

When this repo is used alone or together with Ahrefs, normalize the final result into:

- `selected_tools`
- `selection_reason`
- `target_scope`
- `technical_evidence`
- `market_authority_evidence`
- `conflicts`
- `decision`
- `open_evidence`
- `next_action`

Do not translate Ahrefs estimates into live technical facts. Do not translate seochecker findings into keyword demand, backlink authority, ranking potential or Google index status.
