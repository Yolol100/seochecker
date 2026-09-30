# SEO Checker repository instructions

## Scope
- Deze repository is alleen een accountloze technische SEO controlled-runtime/evidence-adapter voor `seo`.
- Project SEO in Google Drive blijft de bron voor beleid, prioritering en interpretatie.
- De enige inhoudelijke runtime is `.github/workflows/seo-audit.yml`.
- GSC, Ahrefs, analytics, keywordresearch, backlinkstrategie en AI-zichtbaarheid horen buiten deze repository.

## Voor wijzigingen
- Lees `README.md`, `toolkit-contract.json`, de relevante scripts/tests en `.github/workflows/seo-audit.yml`.
- Houd `main` generiek. Klant-, URL- en requestwaarheid hoort in runtime-input of artifacts.
- Commit nooit credentials, tokens, exports of private site-data.

## Validatie

```bash
python3 -m unittest discover -s tests -v
python3 -m py_compile scripts/*.py tests/*.py
```

Bij runtimewijzigingen moeten ook `toolkit-contract.json`, de workflowbedrading en de geraakte tests kloppen.

## Bewijsgrenzen
- Toolmeldingen zijn diagnostics; `seo` bezit het SEO-besluit.
- Lighthouse is labbewijs en geen field-CWV- of rankingbewijs.
- Een groene audit bewijst alleen de uitgevoerde technische checks.
- Een succesvolle Action bewijst geen indexatie, ranking, verkeer, leads of omzet.
- Voer vanuit deze repository geen site-mutaties uit.

## Agent-capability- en impactbeleid

Voordat een agent repository- of externe state wijzigt:

- Classificeer de bedoelde actie als `read_only`, `safe_write` of `high_risk_write`.
- `read_only` mag inspecteren, zoeken, diffen, linten en testen zonder externe state te muteren.
- `safe_write` moet begrensd en omkeerbaar zijn, met target-preflight, stale-state/idempotency-bescherming waar relevant, exacte readback en rollback wanneer het target dit ondersteunt.
- `high_risk_write` omvat destructieve, productie-, deploy-, publicatie-, permission-, securitygevoelige of breed gescopeerde mutaties. Houd die achter expliciete owner/approval en sterkere verificatie.
- Toolbeschikbaarheid, een agentverzoek of groene CI verleent nooit vanzelf extra schrijfrechten.

Bouw vóór niet-triviale bronwijzigingen een begrensde impactcontext uit gewijzigde paden, directe imports/afhankelijkheden, relevante contracten/workflows en de tests die het gedrag bewijzen. Een gegenereerde graph/index is alleen commit-gebonden evidence/cache: geen projectwaarheid, duurzaam geheugen of tweede controller.

GitHub Trending en externe repositories zijn alleen discovery-signalen. Distilleer patronen en verifieer die daarna tegen het ownercontract, actuele primaire/officiële documentatie en lokale regressie-evidence. Kopieer geen code, prompts, assets of configuratie zonder compatibele gebruiksrechten en een expliciete repositoryreden.

