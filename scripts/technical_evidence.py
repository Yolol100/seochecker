#!/usr/bin/env python3
"""Normalize technical crawl evidence, validate URL relationships and compare runs."""
from __future__ import annotations

import argparse
import hashlib
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


def _url_list(values):
    return [url_key(x) for x in _as_list(values) if str(x or "").strip()]


def normalize_record(raw: dict) -> dict:
    requested = raw.get("requested_url") or raw.get("url") or ""
    http = raw.get("http") if isinstance(raw.get("http"), dict) else raw
    final_url = http.get("final_url") or raw.get("final_url") or requested
    blockers = list(dict.fromkeys(_as_list(raw.get("indexability_blockers"))))
    warnings = list(dict.fromkeys(_as_list(raw.get("warnings"))))
    status = http.get("status") if isinstance(http, dict) else raw.get("status")
    try:
        status = int(status) if status is not None else None
    except (TypeError, ValueError):
        status = None
    canonical_values = _as_list(raw.get("canonical"))
    canonical = canonical_values[0] if len(canonical_values) == 1 else ""
    hreflang = raw.get("hreflang") if isinstance(raw.get("hreflang"), list) else []
    xrobots = _as_list(http.get("x_robots_tag") if isinstance(http, dict) else raw.get("x_robots_tag"))
    robots = _as_list(raw.get("robots")) + _as_list(raw.get("googlebot")) + xrobots
    noindex = any("noindex" in str(v).lower() for v in robots)
    indexable = bool(status and 200 <= status < 300 and not noindex and not blockers)
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
            if isinstance(x, dict) and str(x.get("url") or "").strip()
        ],
        "pagination_next": _url_list(raw.get("pagination_next")),
        "pagination_prev": _url_list(raw.get("pagination_prev")),
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


def _fingerprint_urls(records: list[dict]) -> str:
    urls = sorted({r.get("url") for r in records if r.get("url")})
    return hashlib.sha256(("\n".join(urls) + "\n").encode("utf-8")).hexdigest()


def normalize_payload(payload) -> dict:
    records = [normalize_record(x) for x in _extract_records(payload)]
    return {"schema_version": "1.2", "scope": {"url_count": len(records), "url_fingerprint_sha256": _fingerprint_urls(records)}, "records": records}


def _canonical_cycle(start: str, by_url: dict[str, dict]) -> str | None:
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


def _host(url: str | None):
    return (urlsplit(url or "").hostname or "").lower()


def validate_graph(normalized: dict, sitemap_urls=None, *, scope_complete: bool = False) -> dict:
    records = normalized.get("records", [])
    by_url = {r["url"]: r for r in records if r.get("url")}
    issues = []

    def add(issue_type, url, severity, **extra):
        issues.append({"type": issue_type, "url": url, "severity": severity, **extra})

    for r in records:
        url = r.get("url")
        canonical = r.get("canonical")
        if canonical:
            cycle = _canonical_cycle(url, by_url)
            if cycle:
                add("canonical_loop", url, "error", target=cycle)
            if _host(canonical) and _host(url) and _host(canonical) != _host(url):
                add("canonical_cross_domain", url, "info", target=canonical)
            if canonical in by_url:
                target = by_url[canonical]
                if target.get("status") != 200:
                    add("canonical_target_non_200", url, "error", target=canonical)
                if not target.get("indexable"):
                    add("canonical_target_not_indexable", url, "warning", target=canonical)
                target_canonical = target.get("canonical")
                if target_canonical and target_canonical != canonical:
                    add("canonical_chain", url, "warning", via=canonical, target=target_canonical)
        for alt in r.get("hreflang", []):
            target_url = alt.get("url")
            target = by_url.get(target_url)
            if not target:
                add("hreflang_target_not_observed", url, "warning", target=target_url, lang=alt.get("lang"))
                continue
            if target.get("status") != 200:
                add("hreflang_target_non_200", url, "error", target=target_url)
            if not target.get("indexable"):
                add("hreflang_target_not_indexable", url, "error", target=target_url)
            target_canonical = target.get("canonical")
            if target_canonical and target_canonical != target_url:
                add("hreflang_target_canonical_mismatch", url, "warning", target=target_url, canonical=target_canonical)
            if not any(x.get("url") == url for x in target.get("hreflang", [])):
                add("hreflang_return_link_missing", url, "error", target=target_url)
        for rel, opposite in (("pagination_next", "pagination_prev"), ("pagination_prev", "pagination_next")):
            for target_url in r.get(rel, []):
                target = by_url.get(target_url)
                if not target:
                    add("pagination_target_not_observed", url, "warning", target=target_url, relation=rel)
                    continue
                if target.get("status") != 200:
                    add("pagination_target_non_200", url, "error", target=target_url, relation=rel)
                if not target.get("indexable"):
                    add("pagination_target_not_indexable", url, "warning", target=target_url, relation=rel)
                if target.get("canonical") and target.get("canonical") != target_url:
                    add("pagination_target_canonical_mismatch", url, "warning", target=target_url, relation=rel, canonical=target.get("canonical"))
                if url not in target.get(opposite, []):
                    add("pagination_reciprocal_missing", url, "info", target=target_url, relation=rel)
    sitemap_count = None
    if sitemap_urls is not None:
        sitemap = {url_key(x) for x in sitemap_urls if str(x).strip()}
        sitemap_count = len(sitemap)
        crawled = set(by_url)
        for url in sorted(sitemap & crawled):
            r = by_url[url]
            if r.get("final_url") and r.get("final_url") != url:
                add("sitemap_url_redirected", url, "error", target=r.get("final_url"))
            if r.get("status") != 200:
                add("sitemap_url_non_200", url, "error")
            elif not r.get("indexable"):
                add("sitemap_url_not_indexable", url, "error")
            elif r.get("canonical") and r.get("canonical") != url:
                add("sitemap_url_canonical_mismatch", url, "warning", target=r.get("canonical"))
        if scope_complete:
            for url in sorted(sitemap - crawled):
                add("sitemap_url_not_observed", url, "warning")
        for url in sorted(crawled - sitemap):
            if by_url[url].get("indexable"):
                add("indexable_observed_url_missing_from_sitemap", url, "warning")
    limitations = []
    if not scope_complete:
        limitations = [
            "Relationship validation is limited to the observed URL set; unobserved targets remain open evidence.",
            "Sitemap URLs outside the observed runtime set are not classified as crawl failures.",
        ]
    return {
        "schema_version": "1.2",
        "scope_complete": bool(scope_complete),
        "observed_url_count": len(by_url),
        "sitemap_url_count": sitemap_count,
        "issue_count": len(issues),
        "issues": issues,
        "limitations": limitations,
    }


def _record_badness(r: dict) -> tuple:
    return (
        r.get("status") != 200,
        not bool(r.get("indexable")),
        len(r.get("blockers") or []),
        len(r.get("warnings") or []),
    )


def _issue_fingerprint(issue: dict) -> str:
    stable = {
        k: issue.get(k)
        for k in ("type", "url", "target", "via", "relation", "lang", "canonical", "severity")
        if issue.get(k) is not None
    }
    return hashlib.sha256(json.dumps(stable, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def diff_graphs(before_graph: dict | None, after_graph: dict | None) -> dict:
    if before_graph is None or after_graph is None:
        return {"compared": False, "new": [], "resolved": [], "has_regressions": False}
    before_map = {_issue_fingerprint(x): x for x in before_graph.get("issues", []) if isinstance(x, dict)}
    after_map = {_issue_fingerprint(x): x for x in after_graph.get("issues", []) if isinstance(x, dict)}
    new = [after_map[k] for k in sorted(set(after_map) - set(before_map))]
    resolved = [before_map[k] for k in sorted(set(before_map) - set(after_map))]
    regressions = [x for x in new if x.get("severity") in {"error", "warning"}]
    return {
        "compared": True,
        "new": new,
        "resolved": resolved,
        "new_count": len(new),
        "resolved_count": len(resolved),
        "regression_count": len(regressions),
        "has_regressions": bool(regressions),
    }


def diff_runs(before: dict, after: dict, before_graph: dict | None = None, after_graph: dict | None = None) -> dict:
    before_map = {r["url"]: r for r in before.get("records", []) if r.get("url")}
    after_map = {r["url"]: r for r in after.get("records", []) if r.get("url")}
    changed = []
    fields = ("status", "final_url", "indexable", "canonical", "title", "h1", "blockers", "warnings", "hreflang", "pagination_next", "pagination_prev", "observation_layer")
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
            b_bad = _record_badness(b)
            a_bad = _record_badness(a)
            classification = "improved" if a_bad < b_bad else "regressed" if a_bad > b_bad else "changed"
            changed.append({"url": url, "classification": classification, "changes": delta})
    counts: dict[str, int] = {}
    for item in changed:
        counts[item["classification"]] = counts.get(item["classification"], 0) + 1
    graph = diff_graphs(before_graph, after_graph)
    has_regressions = bool(counts.get("regressed") or counts.get("missing_after") or graph["has_regressions"])
    return {
        "schema_version": "1.2",
        "before_url_count": len(before_map),
        "after_url_count": len(after_map),
        "counts": counts,
        "graph": graph,
        "has_regressions": has_regressions,
        "changes": changed,
    }


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
    p.add_argument("--scope-complete", action="store_true")
    d = sub.add_parser("diff")
    d.add_argument("--before", required=True)
    d.add_argument("--after", required=True)
    d.add_argument("--before-graph")
    d.add_argument("--after-graph")
    d.add_argument("--output", required=True)
    d.add_argument("--fail-on-regression", action="store_true")
    args = ap.parse_args()
    if args.command == "normalize":
        normalized = normalize_payload(read_json(args.input))
        write_json(args.output, normalized)
        if args.graph_output:
            sitemap = Path(args.sitemap_list).read_text(encoding="utf-8").splitlines() if args.sitemap_list else None
            write_json(args.graph_output, validate_graph(normalized, sitemap, scope_complete=args.scope_complete))
        return 0
    if bool(args.before_graph) != bool(args.after_graph):
        raise ValueError("before-graph and after-graph must be supplied together")
    before_graph = read_json(args.before_graph) if args.before_graph else None
    after_graph = read_json(args.after_graph) if args.after_graph else None
    diff = diff_runs(read_json(args.before), read_json(args.after), before_graph, after_graph)
    write_json(args.output, diff)
    return 1 if args.fail_on_regression and diff["has_regressions"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
