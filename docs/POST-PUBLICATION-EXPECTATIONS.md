# Post-publication expectation verification

Use `scripts/verify_page_expectations.py` after a draft or staging change is reported live and the SEO owner needs to verify that the public response actually contains the expected release-critical SEO properties.

This is a live evidence checker, not a content generator and not a ranking scorer.

## Input

Pass one page object or a `pages` array. Keep customer/project-specific expectation files in runtime artifacts or another non-default-branch location; do not hardcode them on `main`.

```json
{
  "pages": [
    {
      "url": "https://example.nl/service-city/",
      "expected": {
        "status": 200,
        "indexable": true,
        "title_contains": "Service City",
        "meta_contains": "service city",
        "h1_contains": "Service City",
        "canonical_equals": "/service-city/",
        "required_internal_links": [
          "/service/",
          "/service-inhuren/"
        ]
      }
    }
  ]
}
```

Supported expectations:

- `status`
- `indexable`
- `title_contains`
- `meta_contains`
- `h1_contains`
- `canonical_equals`
- `final_url_equals`
- `required_internal_links`

## Run

```bash
python3 scripts/verify_page_expectations.py expectations.json --report reports/page-expectations.json
```

Exit code `0` means all requested expectations passed. Exit code `1` means at least one requested expectation failed.

## Evidence boundary

The verifier checks the HTTP response observed during that run. It can support a `production_verified` claim only for the exact properties it checked. It does not prove rankings, traffic, conversions, future indexation, JavaScript-rendered DOM state, or plugin UI scores.

The checker includes `meta robots`, `googlebot` and `X-Robots-Tag` when determining the requested `indexable` expectation. It normalizes `www` and trailing slashes for URL/link comparisons to avoid cosmetic mismatches.

## Safety

Only public HTTP(S) targets are accepted. Resolved loopback, private, link-local or otherwise non-global IP addresses are rejected. Do not store customer credentials, secrets or customer-specific expectation payloads permanently on the default branch.
