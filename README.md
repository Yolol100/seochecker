# SEO Checker — Technical SEO Evidence

SEO Checker turns one public website URL into a repeatable technical SEO evidence package.

**Built by:** [Andrew Baeten](https://github.com/Yolol100) · [Portfolio](https://andrewbaeten.nl)

## Eén taak

`publieke URL -> technische live-checks -> crawl/lab/HTML evidence -> artifact`

De repository bepaalt geen SEO-strategie en bevat geen klantwaarheid. Project SEO in Google Drive bepaalt beleid en interpretatie; deze repo levert alleen gecontroleerde technische evidence.

## Workflow

Gebruik **Actions -> SEO Audit -> Run workflow** en geef een publieke HTTPS-URL op.

De audit voert uit:

- HTTP/final URL en indexability-checks;
- meta robots, `X-Robots-Tag`, canonical, sitemap en basismetadata;
- JSON-LD-syntax en gevonden types;
- SiteOne crawl;
- Lighthouse CI labmeting;
- lokale Nu HTML-validatie;
- `reports/evidence-manifest.json` met provenance en artifactinventaris.

Belangrijkste output:

- `reports/evidence-manifest.json`
- `reports/basic-seo.json`
- `reports/siteone.json`
- `reports/siteone.html`
- `reports/lighthouse-summary.json`
- `reports/w3c-nu.json`
- `.lighthouseci/` alleen wanneer ruwe diagnose nodig is

Lees na iedere run eerst `reports/evidence-manifest.json`.

## Post-publication check

`scripts/verify_page_expectations.py` vergelijkt de live HTTP-response/HTML met expliciete runtime-verwachtingen. Het script controleert geen JavaScript-browser-DOM.

Ondersteunde verwachtingen zijn `status`, `indexable`, `title_contains`, `meta_contains`, `h1_contains`, `canonical_equals`, `final_url_equals` en `required_internal_links`.

Voorbeeld:

```json
{
  "url": "https://example.nl/dienst/",
  "expected": {
    "status": 200,
    "indexable": true,
    "title_contains": "Dienst",
    "canonical_equals": "/dienst/",
    "required_internal_links": ["/contact/"]
  }
}
```

```bash
python3 scripts/verify_page_expectations.py expectations.json --report reports/page-expectations.json
```

Commit geen klant-/URL-specifieke expectationbestanden op `main`. Een geslaagde check bewijst alleen de expliciet gecontroleerde live HTTP/HTML-eigenschappen, niet ranking, verkeer, conversies of JavaScript-gerenderde toestand.

## Wat bewust niet in deze repo zit

- GSC-data of GSC OAuth;
- Ahrefs-data of API-keys;
- keyword-, backlink- of AI-zichtbaarheidsstrategie;
- content-/media-/schema-beleid dat al in Project SEO staat;
- ranking-, traffic-, lead- of omzetclaims.

GSC, Ahrefs, analytics en andere databronnen worden buiten deze repo gebruikt en alleen gecombineerd wanneer hun evidenceklasse de SEO-beslissing echt verandert.

## Bewijsgrenzen

- Toolmeldingen zijn diagnostics, geen Google-oordeel.
- Lighthouse is labdata en vervangt geen fielddata/CrUX.
- Een technische audit bewijst geen indexatie, ranking, verkeer of conversie.
- `toolkit-contract.json` is het enige repositorycontract.
- Klant-/run-specifieke waarheid hoort in runtime-input of artifacts, niet permanent op `main`.

## Veiligheid

Private, loopback en link-local targets worden geweigerd. Commit geen credentials, tokens, klantdata of exports.

## Ontwikkeltest

```bash
python3 -m unittest discover -s tests -v
python3 -m py_compile scripts/*.py tests/*.py
```

## Over de ontwikkelaar

Andrew Baeten is Senior WordPress Developer & Web Designer met 10+ jaar ervaring, 90+ WordPress-projecten en beheer van 120+ websites en webshops.

## Licentie

Deze repository bevat momenteel geen open-sourcelicentie. Hergebruik of distributie vereist expliciete toestemming van de rechthebbende.
