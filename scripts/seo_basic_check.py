#!/usr/bin/env python3
import argparse
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

try:
    from .validate_target import validate_target
except ImportError:
    from validate_target import validate_target

USER_AGENT = "WebactueelSEOChecker/1.1 (+https://github.com/Yolol100/seochecker)"


class PublicOnlyRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_target(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_OPENER = build_opener(PublicOnlyRedirectHandler())


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
        if isinstance(t, str):
            found.add(t)
        elif isinstance(t, list):
            found.update(str(x) for x in t)
        for child in value.values():
            found.update(_jsonld_types(child))
    elif isinstance(value, list):
        for child in value:
            found.update(_jsonld_types(child))
    return found


def _normalize_url(value):
    parsed = urlparse(value)
    path = parsed.path or "/"
    return parsed._replace(scheme=parsed.scheme.lower(), netloc=parsed.netloc.lower(), path=path, fragment="").geturl()


def analyze_html(html, base_url):
    parser = PageParser()
    parser.feed(html)
    title = " ".join("".join(parser.title_parts).split())
    descriptions = _meta_values(parser, "name", "description")
    robots = _meta_values(parser, "name", "robots")
    googlebot = _meta_values(parser, "name", "googlebot")
    canonical = list(dict.fromkeys(urljoin(base_url, l.get("href", "")) for l in parser.links if "canonical" in l.get("rel", "").lower().split() and l.get("href")))
    hreflang = [
        {"lang": l.get("hreflang", "").strip().lower(), "url": urljoin(base_url, l.get("href", ""))}
        for l in parser.links
        if "alternate" in l.get("rel", "").lower().split() and l.get("hreflang") and l.get("href")
    ]
    jsonld_errors = []
    jsonld_types = set()
    for raw in parser.jsonld_raw:
        try:
            jsonld_types.update(_jsonld_types(json.loads(raw)))
        except json.JSONDecodeError as exc:
            jsonld_errors.append(f"line {exc.lineno}, column {exc.colno}: {exc.msg}")
    directives = ",".join(robots + googlebot).lower()
    blockers = []
    warnings = []
    if re.search(r"(?:^|[,\s])noindex(?:$|[,\s])", directives):
        blockers.append("meta robots/googlebot bevat noindex")
    if not title:
        warnings.append("title ontbreekt")
    if len(title) > 65:
        warnings.append("title is langer dan 65 tekens")
    if not descriptions:
        warnings.append("meta description ontbreekt")
    elif len(descriptions) > 1:
        warnings.append("meerdere meta descriptions gevonden")
    if descriptions and len(descriptions[0]) > 160:
        warnings.append("meta description is langer dan 160 tekens")
    if len(parser.h1s) == 0:
        warnings.append("H1 ontbreekt")
    elif len(parser.h1s) > 1:
        warnings.append("meerdere H1's gevonden")
    if len(canonical) == 0:
        warnings.append("canonical ontbreekt")
    elif len(canonical) > 1:
        warnings.append("meerdere canonicals gevonden")
    elif _normalize_url(canonical[0]) != _normalize_url(base_url):
        warnings.append("canonical wijst niet naar de uiteindelijke pagina-URL")
    if jsonld_errors:
        warnings.append("ongeldige JSON-LD gevonden")
    langs = [item["lang"] for item in hreflang]
    duplicates = sorted({lang for lang in langs if langs.count(lang) > 1})
    invalid = sorted({lang for lang in langs if lang != "x-default" and not re.fullmatch(r"[a-z]{2,3}(?:-[a-z]{2}|-[a-z]{4})?", lang, re.I)})
    if duplicates:
        warnings.append("dubbele hreflang-taalcodes gevonden")
    if invalid:
        warnings.append("ongeldige of niet-herkende hreflang-taalcodes gevonden")
    return {
        "title": title,
        "title_length": len(title),
        "meta_descriptions": descriptions,
        "robots": robots,
        "googlebot": googlebot,
        "h1": parser.h1s,
        "canonical": canonical,
        "canonical_self_referencing": len(canonical) == 1 and _normalize_url(canonical[0]) == _normalize_url(base_url),
        "hreflang": hreflang,
        "hreflang_duplicate_languages": duplicates,
        "hreflang_invalid_languages": invalid,
        "jsonld_blocks": len(parser.jsonld_raw),
        "jsonld_types": sorted(jsonld_types),
        "jsonld_errors": jsonld_errors,
        "indexability_blockers": blockers,
        "warnings": warnings,
    }


def fetch(url, timeout=20):
    validate_target(url)
    req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml,*/*;q=0.8"})
    with _OPENER.open(req, timeout=timeout) as response:
        validate_target(response.geturl())
        body = response.read(8_000_000)
        charset = response.headers.get_content_charset() or "utf-8"
        return response.status, response.geturl(), response.headers, body.decode(charset, errors="replace")


def probe(url, timeout=10):
    try:
        status, final_url, headers, body = fetch(url, timeout)
        return {"url": url, "status": status, "final_url": final_url, "content_type": headers.get("Content-Type", ""), "body": body}
    except HTTPError as exc:
        return {"url": url, "status": exc.code, "final_url": exc.geturl(), "error": str(exc)}
    except (URLError, TimeoutError, OSError, ValueError) as exc:
        return {"url": url, "status": None, "error": str(exc)}


def run(url):
    page = probe(url, 25)
    result = {"requested_url": url, "http": {k: v for k, v in page.items() if k != "body"}}
    if page.get("status") is None or page.get("status", 999) >= 400:
        result["indexability_blockers"] = [f"pagina niet bruikbaar: HTTP {page.get('status') or 'fout'}"]
        result["warnings"] = []
        return result
    final_url = page["final_url"]
    result.update(analyze_html(page.get("body", ""), final_url))
    origin = f"{urlparse(final_url).scheme}://{urlparse(final_url).netloc}"
    robots_url = urljoin(origin + "/", "robots.txt")
    robots = probe(robots_url)
    robots_body = robots.pop("body", "")
    sitemap_urls = []
    if robots.get("status") == 200:
        for line in robots_body.splitlines():
            if line.lower().startswith("sitemap:"):
                value = line.split(":", 1)[1].strip()
                if value:
                    sitemap_urls.append(value)
    if not sitemap_urls:
        sitemap_urls = [urljoin(origin + "/", "sitemap.xml")]
    sitemap = probe(sitemap_urls[0])
    sitemap.pop("body", None)
    result["robots_txt"] = robots
    result["sitemap_candidates"] = sitemap_urls
    result["sitemap_probe"] = sitemap
    return result


def main():
    parser = argparse.ArgumentParser(description="Evidence-first technical SEO check")
    parser.add_argument("url")
    parser.add_argument("--output", default="-")
    parser.add_argument("--fail-on-indexability", action="store_true")
    args = parser.parse_args()
    try:
        result = run(args.url)
    except Exception as exc:
        result = {"requested_url": args.url, "fatal_error": str(exc), "indexability_blockers": ["controle kon niet worden uitgevoerd"]}
    payload = json.dumps(result, indent=2, ensure_ascii=False)
    if args.output == "-":
        print(payload)
    else:
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(payload + "\n", encoding="utf-8")
        print(path)
    if "fatal_error" in result:
        return 2
    if args.fail_on_indexability and result.get("indexability_blockers"):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
