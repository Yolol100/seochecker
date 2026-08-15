# SEO Checker

Technische SEO-audittool voor publieke websites. De workflow combineert eigen indexeerbaarheidschecks met SiteOne Crawler, Lighthouse CI en de W3C Nu HTML-validator.

## Rol binnen Project SEO

Deze repository heeft bewust één hoofdtaak: **actuele technische evidence van een publieke eigen URL/site leveren**. Hij vervangt Ahrefs niet en roept Ahrefs niet rechtstreeks aan.

- **seochecker:** actuele technische staat, indexeerbaarheids- en crawlchecks, markup/labvalidatie en technische regressie.
- **Ahrefs:** zoekvraag-, concurrent-, ranking-, backlink-, Rank Tracker- en Brand Radar-context.
- **Beide:** alleen wanneer een SEO-besluit zowel actuele technische waarheid als markt-/autoriteitscontext nodig heeft, bijvoorbeeld migratie, pruning/cleanup, redirectprioriteit, broken-backlink recovery of een volledige technische + markt/autoriteitsaudit.
- **Search Console:** blijft de hogere bewijslaag voor Google's indexstatus en eigen Google Search-prestaties.

Zie `SEO-TOOL-CONTRACT.md` voor de beslismatrix en `seo-tool-contract.json` voor het machineleesbare contract. De Project SEO/SEO-Skill-orkestratielaag kiest de tools; deze GitHub Action bevat geen Ahrefs-credentials of Ahrefs-API-aanroepen.

## Wat wordt gecontroleerd

- HTTP-status en uiteindelijke URL
- meta robots / Googlebot `noindex`
- title, meta description, H1 en canonical
- JSON-LD-syntax en gevonden `@type`-waarden
- robots.txt en een sitemap-kandidaat
- SiteOne crawlrapport voor technische, SEO-, performance-, accessibility- en securitysignalen
- Lighthouse CI labmeting
- W3C Nu HTML-validatie

Toolmeldingen en scores zijn diagnostiek. Indexeerbaarheid, crawlbaarheid, zichtbare inhoud en first-party/live bewijs blijven leidend voor SEO-besluiten.

## Audit uitvoeren

1. Open **Actions** in GitHub.
2. Kies **SEO Audit**.
3. Kies **Run workflow**.
4. Vul een volledige publieke `https://`-URL in.
5. Open na afloop het artifact **seo-audit-report**.

De workflow weigert doelen die naar niet-publieke IP-adressen resolven. Dit voorkomt dat de auditrunner als interne netwerkprobe wordt gebruikt.

Repository-readtoegang bewijst niet dat workflow-dispatch beschikbaar is. Als de uitvoeringssurface de GitHub Action niet kan starten, moet de SEO-orkestratielaag de seochecker-uitvoering als `handoff_required` behandelen; Ahrefs mag dan niet stilzwijgend de ontbrekende live technische verificatie vervangen.

## Rapporten

De workflow bewaart maximaal 14 dagen:

- `reports/basic-seo.json`
- `reports/siteone.html`
- `reports/siteone.json`
- `reports/siteone.txt`
- `reports/w3c-nu.json`
- `.lighthouseci/`

## Versies

De workflow gebruikt bewust vaste versies voor reproduceerbaarheid:

- SiteOne Crawler `2.5.1`, download gecontroleerd met SHA-256
- Lighthouse CI `0.15.1`
- `actions/checkout` `v7.0.1`
- `actions/upload-artifact` `v7.0.1`

## Grenzen

- Lighthouse is labdata en vervangt geen Core Web Vitals-fielddata uit CrUX/Search Console.
- JSON-LD-syntaxcontrole bewijst geen Google rich-result eligibility. Gebruik daarvoor waar relevant ook de actuele officiële Google-validator/documentatie.
- De W3C-service en externe sites kunnen tijdelijk onbereikbaar of rate-limited zijn.
- De tool belooft geen rankings, verkeer, leads of AI-citaties.

## Ontwikkeltest

```bash
python3 -m unittest discover -s tests -v
python3 -m py_compile scripts/*.py tests/*.py
```
