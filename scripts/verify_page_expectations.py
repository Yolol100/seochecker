#!/usr/bin/env python3
"""Verify explicit post-publication expectations against safely fetched HTTP HTML."""
from __future__ import annotations

import argparse
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit

try:
    from .safe_http import fetch_text, resolve_public_ips
except ImportError:
    try:
        from scripts.safe_http import fetch_text, resolve_public_ips
    except ImportError:
        from safe_http import fetch_text, resolve_public_ips


class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title_parts: list[str] = []
        self.h1_parts: list[str] = []
        self.links: list[str] = []
        self.meta: dict[str, str] = {}
        self.canonical = ""
        self._in_title = False
        self._in_h1 = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {k.lower(): (v or "") for k, v in attrs}
        tag = tag.lower()
        if tag == "title":
            self._in_title = True
        elif tag == "h1":
            self._in_h1 = True
        elif tag == "a" and values.get("href"):
            self.links.append(values["href"].strip())
        elif tag == "meta":
            key = (values.get("name") or values.get("property") or "").lower()
            if key and values.get("content"):
                self.meta[key] = values["content"].strip()
        elif tag == "link" and "canonical" in values.get("rel", "").lower().split():
            self.canonical = values.get("href", "").strip()

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag == "title":
            self._in_title = False
        elif tag == "h1":
            self._in_h1 = False

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title_parts.append(data)
        if self._in_h1:
            self.h1_parts.append(data)


def norm_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def normalized_url_key(url: str) -> tuple:
    p = urlsplit(url)
    port = p.port or {"http": 80, "https": 443}.get(p.scheme.lower())
    return p.scheme.lower(), (p.hostname or "").lower(), port, p.path or "/", p.query


def public_http_url(url: str) -> bool:
    try:
        resolve_public_ips(url)
        return True
    except (OSError, ValueError):
        return False


def parse_html(html: str, final_url: str, headers: dict[str, str] | None = None) -> dict:
    parser = PageParser()
    parser.feed(html)
    links = []
    for href in parser.links:
        if href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue
        links.append(urljoin(final_url, href))
    robots = parser.meta.get("robots", "")
    googlebot = parser.meta.get("googlebot", "")
    xrobots = (headers or {}).get("x-robots-tag", "")
    directives = " ".join([robots, googlebot, xrobots]).lower()
    return {
        "title": norm_text(" ".join(parser.title_parts)),
        "meta_description": norm_text(parser.meta.get("description", "")),
        "h1": norm_text(" ".join(parser.h1_parts)),
        "canonical": urljoin(final_url, parser.canonical) if parser.canonical else "",
        "links": links,
        "indexable": "noindex" not in directives,
        "robots": robots,
        "googlebot": googlebot,
        "x_robots_tag": xrobots,
    }


def verify_observation(observed: dict, expected: dict, requested_url: str) -> list[str]:
    errors: list[str] = []
    if "status" in expected and observed.get("status") != expected["status"]:
        errors.append(f"status {observed.get('status')} != expected {expected['status']}")
    if expected.get("indexable") is not None and observed.get("indexable") is not expected["indexable"]:
        errors.append(f"indexable {observed.get('indexable')} != expected {expected['indexable']}")
    for field, key in (("title_contains", "title"), ("meta_contains", "meta_description"), ("h1_contains", "h1")):
        needle = expected.get(field)
        if needle and str(needle).casefold() not in str(observed.get(key, "")).casefold():
            errors.append(f"{key} does not contain expected text: {needle}")
    if expected.get("canonical_equals"):
        wanted = urljoin(requested_url, expected["canonical_equals"])
        if normalized_url_key(observed.get("canonical", "")) != normalized_url_key(wanted):
            errors.append(f"canonical {observed.get('canonical') or '<missing>'} != expected {wanted}")
    if expected.get("final_url_equals"):
        wanted = urljoin(requested_url, expected["final_url_equals"])
        if normalized_url_key(observed.get("final_url", "")) != normalized_url_key(wanted):
            errors.append(f"final URL {observed.get('final_url')} != expected {wanted}")
    actual_links = {normalized_url_key(link) for link in observed.get("links", [])}
    for required in expected.get("required_internal_links", []) or []:
        target = urljoin(requested_url, str(required))
        if normalized_url_key(target) not in actual_links:
            errors.append(f"required internal link missing: {required}")
    return errors


def fetch_page(url: str, timeout: int = 20) -> dict:
    response = fetch_text(
        url,
        timeout=timeout,
        max_bytes=3_000_000,
        headers={"User-Agent": "WebactueelSEOChecker/1.6", "Accept": "text/html,application/xhtml+xml,*/*;q=0.8"},
    )
    headers = {k.lower(): v for k, v in response.headers.items()}
    parsed = parse_html(str(response.body), response.url, headers)
    parsed.update({"status": response.status, "final_url": response.url, "connected_ip": response.connected_ip})
    return parsed


def load_pages(payload: object) -> list[dict]:
    if not isinstance(payload, dict):
        raise ValueError("input must be an object or an object with a pages array")
    pages = payload.get("pages") if "pages" in payload else [payload]
    if not isinstance(pages, list) or not pages:
        raise ValueError("pages must be a non-empty array")
    allowed = {"status", "indexable", "title_contains", "meta_contains", "h1_contains", "canonical_equals", "final_url_equals", "required_internal_links"}
    for page in pages:
        if not isinstance(page, dict) or not isinstance(page.get("url"), str) or not page["url"].strip():
            raise ValueError("every page requires a URL")
        expected = page.get("expected")
        if not isinstance(expected, dict) or not expected or set(expected) - allowed:
            raise ValueError("every page requires non-empty supported expectations")
        for key, value in expected.items():
            if key == "status":
                valid = type(value) is int and 100 <= value <= 599
            elif key == "indexable":
                valid = type(value) is bool
            elif key == "required_internal_links":
                valid = isinstance(value, list) and bool(value) and all(isinstance(v, str) and v.strip() for v in value)
            else:
                valid = isinstance(value, str) and bool(value.strip())
            if not valid:
                raise ValueError(f"invalid expectation: {key}")
    return pages


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("input", help="JSON expectation file")
    ap.add_argument("--report", help="optional JSON report path")
    args = ap.parse_args()
    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    pages = load_pages(payload)
    results = []
    overall_errors = 0
    for item in pages:
        url = item["url"].strip()
        expected = item["expected"]
        try:
            observed = fetch_page(url)
            errors = verify_observation(observed, expected, url)
        except Exception as exc:
            observed = {}
            errors = [str(exc)]
        overall_errors += len(errors)
        results.append({"url": url, "status": "passed" if not errors else "failed", "errors": errors, "observed": observed, "expected": expected})
    report = {
        "status": "passed" if overall_errors == 0 else "failed",
        "results": results,
        "limitations": [
            "Proves only properties observed during this run; it does not prove rankings, traffic, conversions, or future indexation.",
            "Checks safely fetched HTTP-response HTML, not a JavaScript browser DOM.",
        ],
    }
    text = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    print(text)
    if args.report:
        Path(args.report).write_text(text + "\n", encoding="utf-8")
    raise SystemExit(0 if report["status"] == "passed" else 1)


if __name__ == "__main__":
    main()
