#!/usr/bin/env python3
"""Extract page URLs from discovered XML sitemaps with strict public-target and size bounds."""
from __future__ import annotations

import argparse
import gzip
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.request import HTTPRedirectHandler, Request, build_opener

from validate_target import validate_target

USER_AGENT = "WebactueelSEOChecker/1.3 (+https://github.com/Yolol100/seochecker)"


class PublicOnlyRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_target(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_OPENER = build_opener(PublicOnlyRedirectHandler())


def fetch_bytes(url: str, max_bytes: int) -> bytes:
    validate_target(url)
    req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/xml,text/xml,*/*;q=0.5"})
    with _OPENER.open(req, timeout=20) as resp:
        validate_target(resp.geturl())
        data = resp.read(max_bytes + 1)
        if len(data) > max_bytes:
            raise ValueError(f"sitemap exceeds max_bytes={max_bytes}: {url}")
        if url.lower().endswith(".gz") or "gzip" in (resp.headers.get("Content-Type", "").lower()):
            data = gzip.decompress(data)
        return data


def parse_locs(data: bytes) -> tuple[str, list[str]]:
    root = ET.fromstring(data)
    kind = root.tag.rsplit("}", 1)[-1].lower()
    locs = []
    for elem in root.iter():
        if elem.tag.rsplit("}", 1)[-1].lower() == "loc" and elem.text and elem.text.strip():
            locs.append(elem.text.strip())
    return kind, locs


def sitemap_seeds(payload: dict) -> list[str]:
    out = []
    for record in payload.get("records", []):
        if not isinstance(record, dict):
            continue
        for url in record.get("sitemap_candidates", []) or []:
            if isinstance(url, str) and url.strip() and url not in out:
                out.append(url.strip())
    return out


def collect(seeds: list[str], max_sitemaps: int, max_urls: int, max_bytes: int) -> tuple[list[str], list[dict]]:
    queue = list(seeds)
    seen_maps = set()
    urls = []
    errors = []
    while queue and len(seen_maps) < max_sitemaps and len(urls) < max_urls:
        sm = queue.pop(0)
        if sm in seen_maps:
            continue
        seen_maps.add(sm)
        try:
            kind, locs = parse_locs(fetch_bytes(sm, max_bytes))
            if kind == "sitemapindex":
                for loc in locs:
                    validate_target(loc)
                    if loc not in seen_maps and loc not in queue and len(seen_maps) + len(queue) < max_sitemaps:
                        queue.append(loc)
            else:
                for loc in locs:
                    validate_target(loc)
                    if loc not in urls:
                        urls.append(loc)
                    if len(urls) >= max_urls:
                        break
        except Exception as exc:
            errors.append({"sitemap": sm, "error": str(exc)})
    return urls, errors


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--input", required=True, help="batch JSON containing sitemap_candidates")
    ap.add_argument("--output", required=True, help="plain text URL list")
    ap.add_argument("--report", required=True, help="JSON extraction report")
    ap.add_argument("--max-sitemaps", type=int, default=100)
    ap.add_argument("--max-urls", type=int, default=10000)
    ap.add_argument("--max-bytes", type=int, default=20_000_000)
    args = ap.parse_args()
    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    seeds = sitemap_seeds(payload)
    urls, errors = collect(seeds, args.max_sitemaps, args.max_urls, args.max_bytes)
    Path(args.output).write_text("".join(f"{u}\n" for u in urls), encoding="utf-8")
    report = {
        "schema_version": "1.0",
        "seed_count": len(seeds),
        "url_count": len(urls),
        "errors": errors,
        "truncated": len(urls) >= args.max_urls,
    }
    Path(args.report).write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(args.report)
    return 0 if seeds else 2


if __name__ == "__main__":
    raise SystemExit(main())
