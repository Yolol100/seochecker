#!/usr/bin/env python3
"""Bridge SiteOne JSON into explicit crawl-scope and rendered evidence contracts."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from urllib.parse import urljoin

try:
    from .technical_evidence import url_key
except ImportError:
    try:
        from scripts.technical_evidence import url_key
    except ImportError:
        from technical_evidence import url_key


def _status(value):
    m = re.match(r"\s*(-?\d+)", str(value or ""))
    return int(m.group(1)) if m else None


def _read_lines(path):
    if not path:
        return []
    return [x.strip() for x in Path(path).read_text(encoding="utf-8").splitlines() if x.strip() and not x.lstrip().startswith("#")]


def _dedupe_urls(values: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        value = str(value or "").strip()
        if not value:
            continue
        key = url_key(value)
        if key and key not in seen:
            seen.add(key)
            out.append(value)
    return out


def extract_page_urls(payload: dict, seed_urls: list[str], max_urls: int):
    if not 1 <= max_urls <= 5000:
        raise ValueError("max_urls must be between 1 and 5000")
    urls = _dedupe_urls(seed_urls)
    seen = {url_key(x) for x in urls}
    discovered = 0
    error_status_count = 0
    for row in payload.get("results", []) or []:
        if not isinstance(row, dict) or row.get("type") != 1:
            continue
        url = str(row.get("url") or "").strip()
        if not url:
            continue
        discovered += 1
        status = _status(row.get("status"))
        if status is None or status >= 400:
            error_status_count += 1
        key = url_key(url)
        if key not in seen:
            urls.append(url)
            seen.add(key)
        if len(urls) > max_urls:
            raise ValueError(f"effective sitewide URL set exceeds max_urls={max_urls}; lower crawl scope or raise the explicit cap")
    options = payload.get("options") if isinstance(payload.get("options"), dict) else {}
    stats = payload.get("stats") if isinstance(payload.get("stats"), dict) else {}
    configured = options.get("maxVisitedUrls")
    try:
        configured = int(configured)
    except (TypeError, ValueError):
        configured = max_urls
    try:
        total_visited = int(stats.get("totalUrls", 0))
    except (TypeError, ValueError):
        total_visited = 0
    limit_reached = bool(configured and total_visited >= configured)
    report = {
        "schema_version": "1.1",
        "crawl_scope": "sitewide",
        "seed_url_count": len(_dedupe_urls(seed_urls)),
        "discovered_html_count": discovered,
        "discovered_error_status_count": error_status_count,
        "effective_url_count": len(urls),
        "siteone_total_visited": total_visited,
        "siteone_max_visited_urls": configured,
        "crawl_limit_reached": limit_reached,
        "scope_complete": not limit_reached,
        "limitations": [
            "Site-wide means all same-scope HTML URLs observed by the configured SiteOne crawl; authentication and robots exclusions remain explicit coverage boundaries."
        ] + (["The SiteOne max-visited-urls cap was reached; do not claim complete site-wide coverage."] if limit_reached else []),
    }
    return urls, report


def extract_page_urls_many(payloads: list[dict], seed_urls: list[str], max_urls: int):
    if not payloads:
        raise ValueError("at least one SiteOne payload is required")
    combined = {"results": [], "options": {}, "stats": {}}
    max_total = 0
    configured = max_urls
    for payload in payloads:
        combined["results"].extend(payload.get("results", []) or [])
        options = payload.get("options") if isinstance(payload.get("options"), dict) else {}
        stats = payload.get("stats") if isinstance(payload.get("stats"), dict) else {}
        try:
            configured = min(configured, int(options.get("maxVisitedUrls", max_urls)))
        except (TypeError, ValueError):
            pass
        try:
            max_total = max(max_total, int(stats.get("totalUrls", 0)))
        except (TypeError, ValueError):
            pass
    combined["options"] = {"maxVisitedUrls": configured}
    combined["stats"] = {"totalUrls": max_total}
    return extract_page_urls(combined, seed_urls, max_urls)


def normalize_rendered(payload: dict, requested_urls: list[str]):
    requested_list = _dedupe_urls(requested_urls)
    requested = {url_key(x) for x in requested_list}
    records = []
    observed: set[str] = set()
    for row in payload.get("results", []) or []:
        if not isinstance(row, dict) or row.get("type") != 1:
            continue
        url = str(row.get("url") or "").strip()
        key = url_key(url)
        if not url or (requested and key not in requested) or key in observed:
            continue
        observed.add(key)
        extras = row.get("extras") if isinstance(row.get("extras"), dict) else {}
        canonical = str(extras.get("Canonical") or "").strip()
        robots = str(extras.get("Robots") or "").strip()
        h1 = str(extras.get("H1") or "").strip()
        records.append({
            "requested_url": url,
            "http": {"status": _status(row.get("status")), "final_url": url},
            "title": str(extras.get("Title") or "").strip(),
            "meta_descriptions": [str(extras.get("Description") or "").strip()] if extras.get("Description") else [],
            "h1": [h1] if h1 else [],
            "canonical": [urljoin(url, canonical)] if canonical else [],
            "robots": [robots] if robots else [],
            "hreflang": [],
            "pagination_next": [],
            "pagination_prev": [],
            "indexability_blockers": ["rendered robots bevat noindex"] if "noindex" in robots.lower() else [],
            "warnings": [],
            "observation_layer": "rendered_dom",
        })
    missing = sorted(requested - observed)
    coverage_complete = not missing and len(observed) == len(requested)
    return {
        "schema_version": "1.1",
        "records": records,
        "coverage": {
            "requested_url_count": len(requested),
            "rendered_record_count": len(records),
            "coverage_complete": coverage_complete,
            "missing_requested_urls": missing,
            "fields": ["status", "title", "description", "h1", "canonical", "robots"],
            "not_exported_reliably_by_siteone_json": ["full hreflang set", "pagination relations", "all duplicate head elements"],
            "acceptance_rule": "Fail closed when requested rendered URLs are missing. Use dedicated browser/DOM evidence when a non-exported rendered head signal can change the SEO decision.",
        },
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="command", required=True)
    b = sub.add_parser("bounded-report")
    b.add_argument("--url-list", required=True)
    b.add_argument("--report", required=True)
    e = sub.add_parser("extract-urls")
    e.add_argument("--input", action="append", required=True)
    e.add_argument("--seed-list")
    e.add_argument("--output", required=True)
    e.add_argument("--report", required=True)
    e.add_argument("--max-urls", type=int, required=True)
    r = sub.add_parser("normalize-rendered")
    r.add_argument("--input", required=True)
    r.add_argument("--requested-list", required=True)
    r.add_argument("--output", required=True)
    args = ap.parse_args()
    if args.command == "bounded-report":
        urls = _dedupe_urls(_read_lines(args.url_list))
        if not urls:
            raise ValueError("bounded URL list is empty")
        if len(urls) > 500:
            raise ValueError("bounded URL list exceeds hard cap 500")
        report = {
            "schema_version": "1.1",
            "crawl_scope": "bounded",
            "effective_url_count": len(urls),
            "scope_complete": True,
            "crawl_limit_reached": False,
            "limitations": ["Coverage is intentionally limited to the explicit runtime URL set."],
        }
        Path(args.report).write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return 0
    if args.command == "extract-urls":
        payloads = [json.loads(Path(path).read_text(encoding="utf-8")) for path in args.input]
        urls, report = extract_page_urls_many(payloads, _read_lines(args.seed_list), args.max_urls)
        Path(args.output).write_text("".join(f"{u}\n" for u in urls), encoding="utf-8")
        Path(args.report).write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return 0
    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    normalized = normalize_rendered(payload, _read_lines(args.requested_list))
    Path(args.output).write_text(json.dumps(normalized, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0 if normalized["coverage"]["coverage_complete"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
