#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse

try:
    from .safe_http import fetch_text
    from .validate_target import validate_target
except ImportError:
    from safe_http import fetch_text
    from validate_target import validate_target

USER_AGENT = "WebactueelSEOChecker/1.7 (+https://github.com/Yolol100/seochecker)"
ROBOTS_MAX_RULES = 10000


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.in_title = False
        self.in_h1 = False
        self.in_jsonld = False
        self.title_parts = []
        self.h1_parts = []
        self.h1s = []
        self.meta = []
        self.links = []
        self.jsonld_raw = []
        self._jsonld_parts = []

    def handle_starttag(self, tag, attrs):
        attrs = {str(k).lower(): (v or "") for k, v in attrs}
        tag = tag.lower()
        if tag == "title":
            self.in_title = True
        elif tag == "h1":
            self.in_h1 = True
            self.h1_parts = []
        elif tag == "meta":
            self.meta.append(attrs)
        elif tag == "link":
            self.links.append(attrs)
        elif tag == "script" and attrs.get("type", "").lower() == "application/ld+json":
            self.in_jsonld = True
            self._jsonld_parts = []

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag == "title":
            self.in_title = False
        elif tag == "h1":
            self.in_h1 = False
            text = " ".join("".join(self.h1_parts).split())
            if text:
                self.h1s.append(text)
        elif tag == "script" and self.in_jsonld:
            self.in_jsonld = False
            raw = "".join(self._jsonld_parts).strip()
            if raw:
                self.jsonld_raw.append(raw)

    def handle_data(self, data):
        if self.in_title:
            self.title_parts.append(data)
        if self.in_h1:
            self.h1_parts.append(data)
        if self.in_jsonld:
            self._jsonld_parts.append(data)


def _meta_values(parser, key, value):
    return [m.get("content", "").strip() for m in parser.meta if m.get(key, "").lower() == value and m.get("content")]


def _jsonld_types(value):
    found = set()
    if isinstance(value, dict):
        t = value.get("@type")
        if isinstance(t, str): found.add(t)
        elif isinstance(t, list): found.update(str(x) for x in t)
        for child in value.values(): found.update(_jsonld_types(child))
    elif isinstance(value, list):
        for child in value: found.update(_jsonld_types(child))
    return found


def _normalize_url(value):
    parsed = urlparse(value)
    path = parsed.path or "/"
    host = (parsed.hostname or "").lower()
    default = (parsed.scheme.lower() == "http" and parsed.port == 80) or (parsed.scheme.lower() == "https" and parsed.port == 443)
    port = "" if not parsed.port or default else f":{parsed.port}"
    return parsed._replace(scheme=parsed.scheme.lower(), netloc=f"{host}{port}", path=path, fragment="").geturl()


def _valid_hreflang(value):
    if value == "x-default": return True
    return bool(re.fullmatch(r"[a-z]{2}(?:-[a-z]{4})?(?:-[a-z]{2})?", value, re.I))


def _x_robots_has_noindex(values):
    for value in values or []:
        raw = str(value).strip().lower()
        if not raw: continue
        if raw.startswith("googlebot:"): raw = raw.split(":", 1)[1]
        elif re.match(r"^[a-z0-9_-]+\s*:", raw): continue
        if re.search(r"(?:^|[,\s])noindex(?:$|[,\s])", raw): return True
    return False


def _rel_urls(parser, base_url, rel_name):
    values = []
    for link in parser.links:
        rels = link.get("rel", "").lower().split()
        href = link.get("href", "").strip()
        if rel_name in rels and href:
            absolute = urljoin(base_url, href)
            if absolute not in values: values.append(absolute)
    return values


def _parse_robots(body: str) -> dict:
    groups = []
    agents = []
    rules = []
    seen_rule = False
    rule_count = 0

    def flush():
        nonlocal agents, rules, seen_rule
        if agents:
            groups.append({"agents": list(dict.fromkeys(agents)), "rules": list(rules)})
        agents = []
        rules = []
        seen_rule = False

    for original in str(body or "").splitlines():
        line = original.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        field, value = line.split(":", 1)
        field = field.strip().lower()
        value = value.strip()
        if field == "user-agent":
            if seen_rule:
                flush()
            if value:
                agents.append(value.lower())
        elif field in {"allow", "disallow"} and agents:
            seen_rule = True
            if field == "disallow" and value == "":
                continue
            rule_count += 1
            if rule_count > ROBOTS_MAX_RULES:
                raise ValueError(f"robots.txt exceeds max rules={ROBOTS_MAX_RULES}")
            rules.append({"directive": field, "pattern": value})
        elif field == "sitemap":
            continue
    flush()
    return {"groups": groups, "rule_count": rule_count}


def _robots_pattern_match(pattern: str, path_query: str) -> bool:
    if pattern == "":
        return False
    anchored = pattern.endswith("$")
    core = pattern[:-1] if anchored else pattern
    regex = "^" + re.escape(core).replace(r"\*", ".*")
    if anchored:
        regex += "$"
    return re.search(regex, path_query) is not None


def _robots_specificity(pattern: str) -> int:
    return len(pattern.replace("*", "").replace("$", ""))


def robots_crawlability(policy: dict, url: str, user_agent: str = "googlebot") -> dict:
    ua = user_agent.lower()
    groups = policy.get("groups", []) if isinstance(policy, dict) else []
    exact = [g for g in groups if ua in (g.get("agents") or [])]
    selected = exact or [g for g in groups if "*" in (g.get("agents") or [])]
    rules = [r for g in selected for r in (g.get("rules") or []) if isinstance(r, dict)]
    parsed = urlparse(url)
    path_query = parsed.path or "/"
    if parsed.query:
        path_query += "?" + parsed.query
    matches = [r for r in rules if _robots_pattern_match(str(r.get("pattern") or ""), path_query)]
    if not matches:
        return {"user_agent": ua, "allowed": True, "matched_rule": None, "selected_group_count": len(selected)}
    matches.sort(key=lambda r: (_robots_specificity(str(r.get("pattern") or "")), r.get("directive") == "allow"), reverse=True)
    winner = matches[0]
    return {
        "user_agent": ua,
        "allowed": winner.get("directive") == "allow",
        "matched_rule": {"directive": winner.get("directive"), "pattern": winner.get("pattern")},
        "selected_group_count": len(selected),
    }


def analyze_html(html, base_url):
    parser = PageParser(); parser.feed(html)
    title = " ".join("".join(parser.title_parts).split())
    descriptions = _meta_values(parser, "name", "description")
    robots = _meta_values(parser, "name", "robots")
    googlebot = _meta_values(parser, "name", "googlebot")
    canonical = _rel_urls(parser, base_url, "canonical")
    hreflang = [{"lang": l.get("hreflang", "").strip().lower(), "url": urljoin(base_url, l.get("href", ""))} for l in parser.links if "alternate" in l.get("rel", "").lower().split() and l.get("hreflang") and l.get("href")]
    pagination_next = _rel_urls(parser, base_url, "next")
    pagination_prev = _rel_urls(parser, base_url, "prev")
    jsonld_errors = []; jsonld_types = set()
    for raw in parser.jsonld_raw:
        try: jsonld_types.update(_jsonld_types(json.loads(raw)))
        except json.JSONDecodeError as exc: jsonld_errors.append(f"line {exc.lineno}, column {exc.colno}: {exc.msg}")
    directives = ",".join(robots + googlebot).lower(); blockers = []; warnings = []
    if re.search(r"(?:^|[,\s])noindex(?:$|[,\s])", directives): blockers.append("meta robots/googlebot bevat noindex")
    if not title: warnings.append("title ontbreekt")
    if not descriptions: warnings.append("meta description ontbreekt")
    elif len(descriptions) > 1: warnings.append("meerdere meta descriptions gevonden")
    if not parser.h1s: warnings.append("H1 ontbreekt")
    if len(canonical) == 0: warnings.append("canonical ontbreekt")
    elif len(canonical) > 1: warnings.append("meerdere canonicals gevonden")
    elif _normalize_url(canonical[0]) != _normalize_url(base_url): warnings.append("canonical wijst niet naar de uiteindelijke pagina-URL")
    if jsonld_errors: warnings.append("ongeldige JSON-LD gevonden")
    langs = [item["lang"] for item in hreflang]
    duplicates = sorted({lang for lang in langs if langs.count(lang) > 1})
    invalid = sorted({lang for lang in langs if not _valid_hreflang(lang)})
    hreflang_self_reference = not hreflang or any(_normalize_url(item["url"]) == _normalize_url(base_url) for item in hreflang)
    if duplicates: warnings.append("dubbele hreflang-taalcodes gevonden")
    if invalid: warnings.append("ongeldige of niet-herkende hreflang-taalcodes gevonden")
    if hreflang and not hreflang_self_reference: warnings.append("hreflang mist zelfverwijzing voor de huidige URL")
    return {"title": title, "title_length": len(title), "meta_descriptions": descriptions, "meta_description_lengths": [len(value) for value in descriptions], "robots": robots, "googlebot": googlebot, "h1": parser.h1s, "h1_count": len(parser.h1s), "canonical": canonical, "canonical_self_referencing": len(canonical) == 1 and _normalize_url(canonical[0]) == _normalize_url(base_url), "hreflang": hreflang, "hreflang_duplicate_languages": duplicates, "hreflang_invalid_languages": invalid, "hreflang_self_reference": hreflang_self_reference, "pagination_next": pagination_next, "pagination_prev": pagination_prev, "jsonld_blocks": len(parser.jsonld_raw), "jsonld_types": sorted(jsonld_types), "jsonld_errors": jsonld_errors, "indexability_blockers": blockers, "warnings": warnings}


def fetch(url, timeout=20):
    validate_target(url)
    response = fetch_text(url, timeout=timeout, max_bytes=8_000_000, headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml,*/*;q=0.8"})
    return response.status, response.url, response.headers, response.body


def probe(url, timeout=10):
    try:
        status, final_url, headers, body = fetch(url, timeout)
        x_robots = headers.get_all("X-Robots-Tag") or []
        return {"url": url, "status": status, "final_url": final_url, "content_type": headers.get("Content-Type", ""), "x_robots_tag": [value.strip() for value in x_robots if value and value.strip()], "body": body}
    except (TimeoutError, OSError, ValueError) as exc:
        return {"url": url, "status": None, "error": str(exc)}


def _origin_key(url: str) -> str:
    p = urlparse(url)
    return f"{p.scheme.lower()}://{p.netloc.lower()}"


def _origin_evidence(final_url: str, origin_cache: dict | None = None):
    cache = origin_cache if origin_cache is not None else {}
    key = _origin_key(final_url)
    if key in cache: return copy.deepcopy(cache[key])
    origin = key
    robots_url = urljoin(origin + "/", "robots.txt")
    robots = probe(robots_url); robots_body = robots.pop("body", "")
    robots_policy = {"groups": [], "rule_count": 0}
    robots_parse_error = None
    if robots.get("status") == 200:
        try:
            robots_policy = _parse_robots(robots_body)
        except ValueError as exc:
            robots_parse_error = str(exc)
    sitemap_urls = []
    if robots.get("status") == 200:
        for line in robots_body.splitlines():
            clean = line.split("#", 1)[0].strip()
            if clean.lower().startswith("sitemap:"):
                value = clean.split(":", 1)[1].strip()
                if value: sitemap_urls.append(value)
    if not sitemap_urls: sitemap_urls = [urljoin(origin + "/", "sitemap.xml")]
    sitemap_urls = list(dict.fromkeys(sitemap_urls)); sitemap_probes = []
    for candidate in sitemap_urls[:10]:
        sitemap = probe(candidate); sitemap.pop("body", None); sitemap_probes.append(sitemap)
    result = {
        "robots_txt": robots,
        "robots_policy": robots_policy,
        "robots_parse_error": robots_parse_error,
        "sitemap_candidates": sitemap_urls,
        "sitemap_probes": sitemap_probes,
        "sitemap_probe": sitemap_probes[0] if sitemap_probes else None,
        "sitemap_probe_truncated": len(sitemap_urls) > len(sitemap_probes),
    }
    cache[key] = copy.deepcopy(result)
    return result


def run(url, origin_cache: dict | None = None):
    page = probe(url, 25)
    result = {"requested_url": url, "http": {k: v for k, v in page.items() if k != "body"}}
    if page.get("status") is None or page.get("status", 999) >= 400:
        result["indexability_blockers"] = [f"pagina niet bruikbaar: HTTP {page.get('status') or 'fout'}"]; result["warnings"] = []; return result
    final_url = page["final_url"]; content_type = page.get("content_type", "").lower(); is_html = not content_type or "text/html" in content_type or "application/xhtml+xml" in content_type
    result["content_type_is_html"] = is_html
    if is_html: result.update(analyze_html(page.get("body", ""), final_url))
    else: result.update({"indexability_blockers": [], "warnings": ["response is geen HTML; HTML-specifieke checks zijn overgeslagen"]})
    if _x_robots_has_noindex(page.get("x_robots_tag")): result.setdefault("indexability_blockers", []).append("X-Robots-Tag bevat noindex voor Googlebot")
    origin_evidence = _origin_evidence(final_url, origin_cache)
    result.update(origin_evidence)
    result["crawlability_blockers"] = []
    if origin_evidence.get("robots_parse_error"):
        result.setdefault("warnings", []).append("robots.txt kon niet betrouwbaar worden geparseerd")
        result["robots_googlebot"] = {"user_agent": "googlebot", "allowed": None, "matched_rule": None, "selected_group_count": 0}
    elif origin_evidence.get("robots_txt", {}).get("status") == 200:
        result["robots_googlebot"] = robots_crawlability(origin_evidence.get("robots_policy") or {}, final_url)
        if result["robots_googlebot"]["allowed"] is False:
            result["crawlability_blockers"].append("robots.txt blokkeert Googlebot voor de uiteindelijke URL")
    else:
        result["robots_googlebot"] = {"user_agent": "googlebot", "allowed": None, "matched_rule": None, "selected_group_count": 0}
    return result


def main():
    parser = argparse.ArgumentParser(description="Evidence-first technical SEO check"); parser.add_argument("url"); parser.add_argument("--output", default="-"); parser.add_argument("--fail-on-indexability", action="store_true"); args = parser.parse_args()
    try: result = run(args.url)
    except Exception as exc: result = {"requested_url": args.url, "fatal_error": str(exc), "indexability_blockers": ["controle kon niet worden uitgevoerd"]}
    payload = json.dumps(result, indent=2, ensure_ascii=False)
    if args.output == "-": print(payload)
    else:
        path = Path(args.output); path.parent.mkdir(parents=True, exist_ok=True); path.write_text(payload + "\n", encoding="utf-8"); print(path)
    if "fatal_error" in result: return 2
    if args.fail_on_indexability and result.get("indexability_blockers"): return 1
    return 0

if __name__ == "__main__": sys.exit(main())
