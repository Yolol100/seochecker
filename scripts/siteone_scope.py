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
    from technical_evidence import url_key


def _status(value):
    m = re.match(r"\s*(-?\d+)", str(value or ""))
    return int(m.group(1)) if m else None


def _read_lines(path):
    if not path:
        return []
    return [x.strip() for x in Path(path).read_text(encoding="utf-8").splitlines() if x.strip() and not x.lstrip().startswith("#")]


def extract_page_urls(payload: dict, seed_urls: list[str], max_urls: int):
    urls = []
    for value in seed_urls:
        if value not in urls:
            urls.append(value)
    discovered = 0
    for row in payload.get("results", []) or []:
        if not isinstance(row, dict) or row.get("type") != 1:
            continue
        status = _status(row.get("status"))
        if status is None or not (200 <= status < 400):
            continue
        url = str(row.get("url") or "").strip()
        if not url:
            continue
        discovered += 1
        if url not in urls:
            urls.append(url)
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
    report = {"schema_version": "1.0", "crawl_scope": "sitewide", "seed_url_count": len(seed_urls), "discovered_html_count": discovered, "effective_url_count": len(urls), "siteone_total_visited": total_visited, "siteone_max_visited_urls": configured, "crawl_limit_reached": limit_reached, "scope_complete": not limit_reached, "limitations": ["Site-wide means all same-scope HTML pages discovered by the configured SiteOne crawl; authentication, robots exclusions and crawler limits still bound coverage."] + (["The SiteOne max-visited-urls cap was reached; do not claim complete site-wide coverage."] if limit_reached else [])}
    return urls, report


def normalize_rendered(payload: dict, requested_urls: list[str]):
    requested = {url_key(x) for x in requested_urls}
    records = []
    for row in payload.get("results", []) or []:
        if not isinstance(row, dict) or row.get("type") != 1:
            continue
        url = str(row.get("url") or "").strip()
        if not url or (requested and url_key(url) not in requested):
            continue
        extras = row.get("extras") if isinstance(row.get("extras"), dict) else {}
        canonical = str(extras.get("Canonical") or "").strip()
        robots = str(extras.get("Robots") or "").strip()
        h1 = str(extras.get("H1") or "").strip()
        records.append({"requested_url": url, "http": {"status": _status(row.get("status")), "final_url": url}, "title": str(extras.get("Title") or "").strip(), "meta_descriptions": [str(extras.get("Description") or "").strip()] if extras.get("Description") else [], "h1": [h1] if h1 else [], "canonical": [urljoin(url, canonical)] if canonical else [], "robots": [robots] if robots else [], "hreflang": [], "pagination_next": [], "pagination_prev": [], "indexability_blockers": ["rendered robots bevat noindex"] if "noindex" in robots.lower() else [], "warnings": [], "observation_layer": "rendered_dom"})
    return {"schema_version": "1.0", "records": records, "coverage": {"requested_url_count": len(requested_urls), "rendered_record_count": len(records), "fields": ["status", "title", "description", "h1", "canonical", "robots"], "not_exported_reliably_by_siteone_json": ["full hreflang set", "pagination relations", "all duplicate head elements"], "acceptance_rule": "Use dedicated browser/DOM evidence when a non-exported rendered head signal can change the SEO decision; do not silently substitute HTTP HTML."}}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="command", required=True)
    b = sub.add_parser("bounded-report")
    b.add_argument("--url-list", required=True)
    b.add_argument("--report", required=True)
    e = sub.add_parser("extract-urls")
    e.add_argument("--input", required=True)
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
        urls = _read_lines(args.url_list)
        report = {"schema_version": "1.0", "crawl_scope": "bounded", "effective_url_count": len(urls), "scope_complete": True, "crawl_limit_reached": False, "limitations": ["Coverage is intentionally limited to the explicit runtime URL set."]}
        Path(args.report).write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return 0
    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    if args.command == "extract-urls":
        urls, report = extract_page_urls(payload, _read_lines(args.seed_list), args.max_urls)
        Path(args.output).write_text("".join(f"{u}\n" for u in urls), encoding="utf-8")
        Path(args.report).write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return 0
    normalized = normalize_rendered(payload, _read_lines(args.requested_list))
    Path(args.output).write_text(json.dumps(normalized, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0 if normalized["records"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
