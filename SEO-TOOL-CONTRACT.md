# SEO Tool Contract: seochecker + GSC + Ahrefs

Deze repository levert reproduceerbare SEO-evidence voor een expliciete publieke owned URL/site. Hij heeft een accountloze technische kern en een optionele full-diagnostic laag.

## Bronrollen

### Technische kern

Beantwoordt: **wat is technisch waar op de publieke URL/site tijdens deze run?**

Gebruik voor:

- HTTP/final URL en redirects
- robots/noindex, canonical en sitemap
- title, meta description, H1
- HTML lang en hreflang op de gekozen URL
- JSON-LD syntax/types
- SiteOne technische crawl
- Lighthouse CI labdata
- W3C Nu HTML-validatie

### Google Search Console

Beantwoordt: **wat ziet Google op deze eigen property en hoe veranderde de eigen Google Search-performance?**

Gebruik voor:

- clicks, impressions, CTR en gemiddelde positie
- datum- en landsegmentatie
- query- en page-performance
- URL Inspection indexstatus/canonical/crawlstatus

GSC heeft voor eigen Google-index/status en owned Search-performance voorrang op Ahrefs-schattingen.

### Ahrefs

Beantwoordt: **welke backlink-, authority- en externe search-context ziet Ahrefs?**

Gebruik voor:

- referring-domain historie
- backlink stats
- anchorpatronen
- Ahrefs spamclassificatie in een begrensde sample

Ahrefs-data is third-party diagnostiek en wordt nooit vertaald naar een Google-penalty zonder Google-evidence.

## Workflows

### `SEO Audit`

- Bestand: `.github/workflows/seo-audit.yml`
- Input: publieke URL
- Credentials: geen
- Artifact: `seo-audit-report`
- Capability: `technical-crawl`

### `Full SEO Diagnostic`

- Bestand: `.github/workflows/full-seo-diagnostic.yml`
- Input: publieke URL + optionele taal/land/GSC-property
- Credentials: technisch geen; GSC/Ahrefs optioneel via secrets
- Artifact: `seo-diagnostic-report`
- Capabilities: `technical-crawl`, `owned-search-diagnostic`, `backlink-diagnostic`, `combined-diagnostic`

## Evidence precedence

1. Google's indexstatus en eigen Google Search performance: **Search Console**.
2. Huidige HTTP, directives, canonical, markup en crawlstaat: **actuele seochecker/live evidence**.
3. Ahrefs proprietary backlink/ranking metrics: **Ahrefs als bron voor zijn eigen dataset**.
4. Bij conflict: vergelijk datum, scope en property/target; gemiddelde waarden nooit weg.

## Beslisregels

- Bewezen `noindex`, robots/canonical/fetchproblemen of GSC URL Inspection failures gaan vóór backlinkhypotheses.
- Een sterke GSC-daling met een technisch indexeerbare URL wijst op een ranking/quality/algorithm-vraag, niet automatisch op de-indexatie.
- Spamachtige anchors/refdomains zijn een backlinkspamsignaal, geen bewezen straf.
- Ontbrekende credentials leveren `open_evidence`, geen ingevulde schatting.
- Manual Actions en Security Issues blijven een afzonderlijke GSC UI-check.

## Runtime- en securityregel

- Alleen publieke HTTP(S)-targets.
- Secrets alleen via GitHub Actions secrets.
- Geen klant-/targetspecifieke hardcoding op `main`.
- Repository-readtoegang bewijst niet dat een workflow daadwerkelijk is uitgevoerd; resultaatclaims vereisen een echte run + artifact/logs.
