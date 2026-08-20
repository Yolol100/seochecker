#!/usr/bin/env python3
import argparse
import json
from html.parser import HTMLParser
from pathlib import Path

from seo_basic_check import analyze_html, fetch


class HtmlLangParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.html_lang = None

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "html" and self.html_lang is None:
            values = {str(k).lower(): (v or "") for k, v in attrs}
            self.html_lang = values.get("lang", "").strip() or None


def extract_html_lang(html):
    parser = HtmlLangParser()
    parser.feed(html)
    return parser.html_lang


def language_matches(html_lang, expected_lang):
    if not expected_lang:
        return None
    if not html_lang:
        return False
    actual = html_lang.lower().replace("_", "-")
    expected = expected_lang.lower().replace("_", "-")
    return actual == expected or actual.startswith(expected + "-") or expected.startswith(actual + "-")


def build_report(url, expected_lang):
    status, final_url, headers, html = fetch(url, 25)
    seo = analyze_html(html, final_url)
    html_lang = extract_html_lang(html)
    match = language_matches(html_lang, expected_lang)
    return {
        "status": "ok",
        "requested_url": url,
        "final_url": final_url,
        "http_status": status,
        "content_type": headers.get("Content-Type", ""),
        "expected_lang": expected_lang or None,
        "html_lang": html_lang,
        "language_matches_expected": match,
        "hreflang_languages": [x.get("lang") for x in seo.get("hreflang", [])],
        "hreflang": seo.get("hreflang", []),
        "warnings": ([] if match is not False else ["html lang ontbreekt of past niet bij de verwachte taal"]),
        "limitations": ["Deze probe controleert de opgegeven URL; een volledige meertalige sitestructuur vereist crawl-/GSC-evidence."],
    }


def main():
    parser = argparse.ArgumentParser(description="HTML lang and hreflang probe")
    parser.add_argument("url")
    parser.add_argument("--expected-lang", default="")
    parser.add_argument("--output", default="reports/language-report.json")
    args = parser.parse_args()
    try:
        result = build_report(args.url, args.expected_lang)
    except Exception as exc:
        result = {"status": "error", "error": str(exc), "requested_url": args.url}
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
