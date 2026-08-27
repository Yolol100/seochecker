## 3. Post-publication verwachting controleren

Na een content- of metadatawijziging kunt u de gerenderde live pagina vergelijken met expliciete releaseverwachtingen via `scripts/verify_page_expectations.py`.

De checker kan onder andere HTTP-status, final URL, indexability, title, meta description, H1, canonical en verplichte interne links verifiëren. Gebruik alleen runtime-input voor klant- of paginaspecifieke verwachtingen; commit zulke gegevens niet op `main`.

Voorbeeld:

```bash
python3 scripts/verify_page_expectations.py expectations.json --output reports/page-expectations.json
```

Zie `docs/POST-PUBLICATION-EXPECTATIONS.md` voor het JSON-contract, voorbeelden en bewijsgrenzen. Een geslaagde expectation-check bewijst alleen de eigenschappen die tijdens die run zijn gecontroleerd; hij bewijst geen rankings, verkeer of conversies.
