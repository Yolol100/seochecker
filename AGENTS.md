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
