# SEO Checker

Herbruikbare SEO-audittool voor publieke websites. De repository heeft twee workflows:

- **SEO Audit** — volledig accountloos: technische live-checks, SiteOne crawl, Lighthouse CI en HTML-validatie.
- **Full SEO Diagnostic** — dezelfde technische checks plus optionele Google Search Console- en Ahrefs-data, waarna alles in één evidence-first rapport wordt samengebracht.

De workflows houden bronrollen bewust uit elkaar: technische live-data bewijst wat de site nu serveert, Search Console is de hoogste bewijslaag voor eigen Google-index/status en search performance, en Ahrefs levert third-party backlink- en rankingcontext.

## Wat wordt gecontroleerd

Accountloos, bij iedere technische audit:

- HTTP-status, redirects en uiteindelijke URL
- meta robots / Googlebot `noindex`
- title, meta description, H1 en canonical
- hreflang op de gekozen URL
- robots.txt en sitemap-kandidaat
- JSON-LD-syntax en gevonden `@type`-waarden
- SiteOne crawlrapport
- Lighthouse CI labmeting
- lokale W3C Nu HTML-validatie

Extra in **Full SEO Diagnostic**:

- HTML `lang` tegenover de verwachte doeltaal
- GSC clicks, impressions, CTR en positie over tijd
- GSC vergelijking laatste 28 dagen versus vorige 28 dagen
- sterkste 7-daagse daling in impressions
- target-country prestaties en top queries/pages
- GSC URL Inspection voor de opgegeven URL
- Ahrefs referring-domain historie
- Ahrefs backlinks stats
- verdachte/spamachtige anchorpatronen
- sample van referring domains met Ahrefs `is_spam`
- gecombineerd `diagnostic-summary.json` + `diagnostic-summary.md`

## 1. Accountloze technische audit

1. Open **Actions**.
2. Kies **SEO Audit**.
3. Klik **Run workflow**.
4. Vul een publieke `https://`-URL in.
5. Download na afloop artifact **seo-audit-report**.

Hiervoor zijn geen API-keys, MCP-servers of andere accounts nodig dan GitHub zelf.

## 2. Volledige SEO-diagnose

1. Open **Actions**.
2. Kies **Full SEO Diagnostic**.
3. Klik **Run workflow**.
4. Vul minimaal de publieke URL in.
5. Vul indien beschikbaar de exacte GSC property in, bijvoorbeeld `sc-domain:example.com`.
6. Laat GSC/Ahrefs aangevinkt als de bijbehorende secrets zijn ingesteld.
7. Download artifact **seo-diagnostic-report**.

Belangrijkste output:

- `reports/diagnostic-summary.md`
- `reports/diagnostic-summary.json`
- `reports/basic-seo.json`
- `reports/language-report.json`
- `reports/gsc-report.json`
- `reports/ahrefs-report.json`
- `reports/siteone.json`
- `reports/siteone.html`
- `reports/w3c-nu.json`
- `.lighthouseci/`

## GSC koppelen

De repository gebruikt voor GSC een gewone OAuth 2.0 refresh-tokenconfiguratie. Dat voorkomt dat een workflow interactieve login nodig heeft.

Benodigde GitHub Actions secrets:

- `GSC_CLIENT_ID`
- `GSC_CLIENT_SECRET`
- `GSC_REFRESH_TOKEN`

De Google-account achter het refresh token moet minimaal leesrechten hebben op de Search Console-property. Gebruik scope `https://www.googleapis.com/auth/webmasters.readonly`.

Google vereist voor de Search Console API een Google Cloud-project, geactiveerde Search Console API en OAuth-credentials. Dit is een eenmalige setup; daarna blijven de credentials als GitHub Actions secrets opgeslagen.

Zie `docs/INTEGRATIONS.md` voor de setup en bewijsgrenzen.

## Ahrefs koppelen

Optionele GitHub Actions secret:

- `AHREFS_API_KEY`

De workflow gebruikt Ahrefs API v3 en vraagt alleen de data op die de diagnose ondersteunt: backlink stats, referring-domain history, anchors en een beperkte referring-domain sample.

Geen Ahrefs key? De workflow blijft werken en schrijft `status: not_configured` in `reports/ahrefs-report.json`. De technische audit blijft gewoon uitvoerbaar.

## Algemene content- en mediaregels

Naast de technische audit bevat deze repository generieke operationele SEO-richtlijnen voor contentproductie en publicatie-QA. Zie `docs/CONTENT-MEDIA-GUIDELINES.md` voor:

- beschrijvende bestandsnamen en feitelijke alt-tekst zonder keyword stuffing;
- featured/preferred-image en rendered-metadata controle;
- fail-closed automatische koppeling van media of content aan exacte targets;
- interne linkmatrices zonder geforceerde all-to-all linking;
- taxonomie zonder dunne of dubbele categorieën;
- statusovergangen zoals `draft -> reported_live -> production_verified`;
- bewijsgrenzen tussen CMS/configuratie en daadwerkelijk gerenderde live output.

## Bewijsgrenzen

- Een Ahrefs `is_spam`-label is geen Google-oordeel.
- Ahrefs `first_seen` is wanneer Ahrefs een backlink voor het eerst vond, niet noodzakelijk de creatiedatum van de link.
- Een sterk spamachtig backlinkprofiel bewijst op zichzelf geen Google-penalty.
- URL Inspection API toont Google's indexstatus voor de URL; het is geen live URL-test.
- Search Console **Handmatige acties** en **Beveiligingsproblemen** blijven een aparte handmatige controle.
- Lighthouse is labdata en vervangt geen Core Web Vitals-fielddata.
- Een CMS-instelling, importbestand of code-snippet bewijst niet dat dezelfde toestand live wordt gerenderd.
- Een melding dat content live staat is `reported_live`; productieclaims vragen een nieuwe live controle.
- Het rapport mag geen ranking-, traffic- of penaltyclaim maken die niet door de juiste bron wordt gedragen.

## Veiligheid

- Private, loopback en link-local targets worden geweigerd.
- Commit nooit klantcredentials, OAuth-tokens, Ahrefs keys of klant-specifieke exports in deze publieke repository.
- Gebruik GitHub Actions secrets voor credentials.
- Klant-/run-specifieke waarheid hoort in artifacts of een tijdelijke runtime-branch, niet permanent op `main`.
- Automatische writes naar content/media moeten exact targeten en stoppen wanneer geen uniek geldig doel is gevonden.

## Ontwikkeltest

```bash
python3 -m unittest discover -s tests -v
python3 -m py_compile scripts/*.py tests/*.py
```

Zie `SEO-TOOL-CONTRACT.md` en `seo-tool-contract.json` voor de formele bron- en capabilitygrenzen.
