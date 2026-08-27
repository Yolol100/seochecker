#!/usr/bin/env python3
"""Verify post-publication expectations against a public rendered HTML page.

Input is a JSON file with either one object or {"pages": [...]}.
This tool proves only the requested live page properties observed during the run.
"""
from __future__ import annotations

import argparse
import ipaddress
import json
import re
import socket
import sys
import urllib.error
import urllib.request
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit


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
        elif tag == "link" and values.get("rel", "").lower() == "canonical":
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


def normalized_url_key(url: str) -> tuple[str, str]:
    p = urlsplit(url)
    host = (p.hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    path = re.sub(r"/+", "/", p.path or "/")
    if path != "/":
        path = path.rstrip("/")
    return host, path


def public_http_url(url: str) -> bool:
    p = urlsplit(url)
    if p.scheme not in {"http", "https"} or not p.hostname:
        return False
    try:
        infos = socket.getaddrinfo(p.hostname, p.port or (443 if p.scheme == "https" else 80), type=socket.SOCK_STREAM)
    except socket.gaierror:
        return False
    for info in infos:
        try:
            ip = ipaddress.ip_address(info[4][0])
        except ValueError:
            return False
        if not ip.is_global:
            return False
    return True


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
    if not public_http_url(url):
        raise ValueError("target must resolve only to public HTTP(S) addresses")
    req = urllib.request.Request(url, headers={"User-Agent": "Webactueel-SEOChecker/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read(3_000_000).decode(resp.headers.get_content_charset() or "utf-8", errors="replace")
            final_url = resp.geturl()
            headers = {k.lower(): v for k, v in resp.headers.items()}
            parsed = parse_html(body, final_url, headers)
            parsed.update({"status": resp.status, "final_url": final_url})
            return parsed
    except urllib.error.HTTPError as exc:
        body = exc.read(3_000_000).decode(exc.headers.get_content_charset() or "utf-8", errors="replace")
        headers = {k.lower(): v for k, v in exc.headers.items()}
        parsed = parse_html(body, exc.geturl(), headers)
        parsed.update({"status": exc.code, "final_url": exc.geturl()})
        return parsed


def load_pages(payload: object) -> list[dict]:
    if isinstance(payload, dict) and isinstance(payload.get("pages"), list):
        return payload["pages"]
    if isinstance(payload, dict):
        return [payload]
    raise ValueError("input must be an object or an object with a pages array")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("input", help="JSON expectation file")
    ap.add_argument("--report", help="optional JSON report path")
    args = ap.parse_args()
    payload = json.load(open(args.input, encoding="utf-8"))
    pages = load_pages(payload)
    results = []
    overall_errors = 0
    for item in pages:
        url = str(item.get("url") or "").strip()
        expected = item.get("expected") or {}
        if not url:
            results.append({"url": url, "status": "failed", "errors": ["missing url"]})
            overall_errors += 1
            continue
        try:
            observed = fetch_page(url)
            errors = verify_observation(observed, expected, url)
        except Exception as exc:
            observed = {}
            errors = [str(exc)]
        overall_errors += len(errors)
        results.append({"url": url, "status": "passed" if not errors else "failed", "errors": errors, "observed": observed, "expected": expected})
    report = {"status": "passed" if overall_errors == 0 else "failed", "results": results, "limitations": [
        "Proves only properties observed during this run; it does not prove rankings, traffic, conversions, or future indexation.",
        "Checks rendered response HTML from the HTTP fetch, not a JavaScript browser DOM.",
    ]}
    text = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    print(text)
    if args.report:
        open(args.report, "w", encoding="utf-8").write(text + "\n")
    raise SystemExit(0 if report["status"] == "passed" else 1)


if __name__ == "__main__":
    main()
