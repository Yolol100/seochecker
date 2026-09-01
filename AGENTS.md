# SEO Checker repository instructions

## Scope
- This repository is a technical SEO controlled-runtime and evidence adapter for `seo`; it does not define SEO policy, prioritization, search-engine rules or final SEO decisions.
- Project SEO on the registered Google Drive source set remains project truth. `webactueel-workflow` remains the controller for cross-skill routing, source selection and workflow closure.
- Prefer native connected SEO/analytics apps, Site Tools or browser inspection when they can produce the required evidence class. Use this repository for crawl, Lighthouse, Nu HTML or reproducible technical regression evidence that native inspection does not replace.

## Before changing files
- Read `README.md`, `SEO-TOOL-CONTRACT.md`, `seo-tool-contract.json`, the relevant scripts/tests and `.github/workflows/seo-audit.yml`.
- Keep `main` generic. Client/page expectations and concrete audit requests belong in runtime input, temporary `runtime/**` branches or run-scoped artifacts.
- Never commit GSC OAuth credentials, Ahrefs keys, client exports or private site data.

## Validation
Run the repository's documented deterministic checks:

```bash
python3 -m unittest discover -s tests -v
python3 -m py_compile scripts/*.py tests/*.py
```

When audit behavior, request contracts, evidence manifests or workflows change, exercise the smallest matching workflow/test path and confirm artifact correlation.

## Evidence boundaries
- Search Console and Ahrefs metrics keep their own source semantics; third-party estimates never become primary truth.
- Lighthouse is lab evidence and does not prove field Core Web Vitals or ranking impact.
- A green audit proves only the checks actually executed. `seo` interprets and prioritizes the evidence; a successful Action is not an SEO decision, index-state guarantee or ranking claim.
- Do not merge, publish or execute site mutations merely because repository checks are green.
