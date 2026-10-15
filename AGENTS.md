# SEO Checker — agentcontract

## Rol
- Read-only technische SEO-evidence voor `seo`; live Project SEO bepaalt beleid en besluit. Geen GSC/Ahrefs-dataset, rankings, sitewrites of tweede controller.
- Lees voor changes `README.md`, `toolkit-contract.json`, de geraakte scripts/tests en `.github/workflows/seo-audit.yml`.

## Veiligheid
- Houd `main` generiek: geen klant-URL's, requeststate, exports, secrets of runtime-artifacts. Gebruik begrensde public-URL-scans, veilige netwerk-/redirectcontroles en bestaande scope-capability gates.
- Classificeer acties `read_only`, `safe_write` (preflight, klein, omkeerbaar, readback) of `high_risk_write` (uitdrukkelijk akkoord). Deze repo doet nooit live site-mutaties.
- Controleer actuele Google-claims via officiële Search Central-documentatie; externe code, YouTube en Trending zijn alleen discovery, geen bewijs of automatische import.

## Test en claim
- `python3 -m unittest discover -s tests -v`
- `python3 -m py_compile scripts/*.py tests/*.py`
- Synchroniseer gewijzigde runtimecode met `toolkit-contract.json`, workflows en geraakte tests.
- Lighthouse is labbewijs; crawl- en robots-uitvoer zijn begrensde observaties. Groene CI bewijst geen indexatie, rankings, verkeer, leads, field CWV of productieacceptatie. Meld onbekende/truncated resultaten expliciet.
