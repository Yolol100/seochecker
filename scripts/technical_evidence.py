#!/usr/bin/env python3
"""Normalize technical crawl evidence and compare technical SEO runs.

This module deliberately consumes generic runtime JSON. It does not call Ahrefs or GSC and
contains no project/target truth. External tools select URLs; this runtime verifies technical state.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit


def url_key(value: str) -> str:
    p = urlsplit(str(value or "").strip())
    scheme = p.scheme.lower()
    host = (p.hostname or "").lower()
    port = p.port
    default = (scheme == "http" and port == 80) or (scheme == "https" and port == 443)
    netloc = host if not port or default else f"{host}:{port}"
    return urlunsplit((scheme, netloc, p.path or "/", p.query, ""))


def _as_list(value):
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def normalize_record(raw: dict) -> dict:
    requested = raw.get("requested_url") or raw.get("url") or ""
    http = raw.get("http") if isinstance(raw.get("http"), dict) else raw
    final_url = http.get("final_url") or raw.get("final_url") or requested
    blockers = list(dict.fromkeys(_as_list(raw.get("indexability_blockers"))))
    warnings = list(dict.fromkeys(_as_list(raw.get("warnings"))))
    status = http.get("status") if isinstance(http, dict) else raw.get("status")
    canonical_values = _as_list(raw.get("canonical"))
    canonical = canonical_values[0] if len(canonical_values) == 1 else ""
    hreflang = raw.get("hreflang") if isinstance(raw.get("hreflang"), list) else []
    xrobots = _as_list(http.get("x_robots_tag") if isinstance(http, dict) else raw.get("x_robots_tag"))
    robots = _as_list(raw.get("robots")) + _as_list(raw.get("googlebot")) + xrobots
    noindex = any("noindex" in str(v).lower() for v in robots)
    indexable = bool(status and 200 <= int(status) < 300 and not noindex and not blockers)
    return {
        "url": url_key(requested),
        "requested_url": requested,
        "final_url": url_key(final_url),
        "status": status,
        "indexable": indexable,
        "canonical": url_key(canonical) if canonical else None,
        "title": raw.get("title") or None,
        "h1": raw.get("h1") or [],
        "hreflang": [
            {"lang": str(x.get("lang") or "").lower(), "url": url_key(x.get("url") or "")}
            for x in hreflang
            if isinstance(x, dict)
        ],
        "blockers": blockers,
        "warnings": warnings,
        "observation_layer": raw.get("observation_layer") or "http_response_html",
    }


def _extract_records(payload) -> list[dict]:
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if not isinstance(payload, dict):
        raise ValueError("input JSON must be an object or array")
    for key in ("records", "pages", "results", "urls"):
        if isinstance(payload.get(key), list):
            return [x for x in payload[key] if isinstance(x, dict)]
    return [payload]


def normalize_payload(payload) -> dict:
    records = [normalize_record(x) for x in _extract_records(payload)]
    return {"schema_version": "1.0", "records": records}


def _canonical_cycle(start: str, by_url: dict[str, dict]) -> str | None:
    """Return the repeated URL when a real canonical cycle exists; self canonicals terminate."""
    seen = set()
    current = start
    while current in by_url:
        if current in seen:
            return current
        seen.add(current)
        nxt = by_url[current].get("canonical")
        if not nxt or nxt == current:
            return None
        current = nxt
    return None


def validate_graph(normalized: dict, sitemap_urls=None) -> dict:
    records = normalized.get("records", [])
    by_url = {r["url"]: r for r in records if r.get("url")}
    issues = []

    for r in records:
        url = r.get("url")
        canonical = r.get("canonical")
        if canonical:
            cycle = _canonical_cycle(url, by_url)
            if cycle:
                issues.append({"type": "canonical_loop", "url": url, "target": cycle, "severity": "error"})
            if canonical in by_url:
                target = by_url[canonical]
                if target.get("status") != 200:
                    issues.append({"type": "canonical_target_non_200", "url": url, "target": canonical, "severity": "error"})
                if not target.get("indexable"):
                    issues.append({"type": "canonical_target_not_indexable", "url": url, "target": canonical, "severity": "warning"})
        for alt in r.get("hreflang", []):
            target_url = alt.get("url")
            target = by_url.get(target_url)
            if not target:
                issues.append({
                    "type": "hreflang_target_not_observed",
                    "url": url,
                    "target": target_url,
                    "lang": alt.get("lang"),
                    "severity": "warning",
                })
                continue
            if target.get("status") != 200:
                issues.append({"type": "hreflang_target_non_200", "url": url, "target": target_url, "severity": "error"})
            if not target.get("indexable"):
                issues.append({"type": "hreflang_target_not_indexable", "url": url, "target": target_url, "severity": "error"})
            reciprocal = any(x.get("url") == url for x in target.get("hreflang", []))
            if not reciprocal:
                issues.append({"type": "hreflang_return_link_missing", "url": url, "target": target_url, "severity": "error"})

    sitemap_count = None
    if sitemap_urls is not None:
        sitemap = {url_key(x) for x in sitemap_urls if str(x).strip()}
        sitemap_count = len(sitemap)
        crawled = set(by_url)
        # A bounded runtime URL set is not a full-site crawl. Only assert sitemap health for
        # URLs that were actually observed; do not turn unobserved sitemap URLs into false issues.
        for url in sorted(sitemap & crawled):
            r = by_url[url]
            if r.get("status") != 200:
                issues.append({"type": "sitemap_url_non_200", "url": url, "severity": "error"})
            elif not r.get("indexable"):
                issues.append({"type": "sitemap_url_not_indexable", "url": url, "severity": "error"})
            elif r.get("canonical") and r.get("canonical") != url:
                issues.append({"type": "sitemap_url_canonical_mismatch", "url": url, "target": r.get("canonical"), "severity": "warning"})
        for url in sorted(crawled - sitemap):
            if by_url[url].get("indexable"):
                issues.append({"type": "indexable_observed_url_missing_from_sitemap", "url": url, "severity": "warning"})

    return {
        "schema_version": "1.0",
        "observed_url_count": len(by_url),
        "sitemap_url_count": sitemap_count,
        "issue_count": len(issues),
        "issues": issues,
        "limitations": [
            "Sitemap reconciliation is scoped to observed runtime URLs unless a caller explicitly supplies a complete observed crawl.",
            "hreflang targets outside the observed URL set remain open evidence, not proven failures.",
        ],
    }


def diff_runs(before: dict, after: dict) -> dict:
    before_map = {r["url"]: r for r in before.get("records", [])}
    after_map = {r["url"]: r for r in after.get("records", [])}
    changed = []
    fields = ("status", "final_url", "indexable", "canonical", "title", "h1", "blockers", "warnings", "hreflang")
    for url in sorted(set(before_map) | set(after_map)):
        b, a = before_map.get(url), after_map.get(url)
        if b is None:
            changed.append({"url": url, "classification": "new_url", "changes": {}})
            continue
        if a is None:
            changed.append({"url": url, "classification": "missing_after", "changes": {}})
            continue
        delta = {f: {"before": b.get(f), "after": a.get(f)} for f in fields if b.get(f) != a.get(f)}
        if delta:
            b_bad = bool(b.get("blockers")) or b.get("status") != 200
            a_bad = bool(a.get("blockers")) or a.get("status") != 200
            classification = "improved" if b_bad and not a_bad else "regressed" if not b_bad and a_bad else "changed"
            changed.append({"url": url, "classification": classification, "changes": delta})
    counts = {}
    for item in changed:
        counts[item["classification"]] = counts.get(item["classification"], 0) + 1
    return {"schema_version": "1.0", "counts": counts, "changes": changed}


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, payload):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="command", required=True)
    p = sub.add_parser("normalize")
    p.add_argument("--input", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--sitemap-list")
    p.add_argument("--graph-output")
    d = sub.add_parser("diff")
    d.add_argument("--before", required=True)
    d.add_argument("--after", required=True)
    d.add_argument("--output", required=True)
    args = ap.parse_args()
    if args.command == "normalize":
        normalized = normalize_payload(read_json(args.input))
        write_json(args.output, normalized)
        if args.graph_output:
            sitemap = Path(args.sitemap_list).read_text(encoding="utf-8").splitlines() if args.sitemap_list else None
            write_json(args.graph_output, validate_graph(normalized, sitemap))
    else:
        write_json(args.output, diff_runs(read_json(args.before), read_json(args.after)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
