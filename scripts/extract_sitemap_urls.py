#!/usr/bin/env python3
"""Extract page URLs from discovered XML sitemaps with strict public-target and size bounds."""
from __future__ import annotations

import argparse
import gzip
import io
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.request import HTTPRedirectHandler

try:
    from .safe_http import fetch_bytes as safe_fetch_bytes
    from .validate_target import validate_target
except ImportError:
    from safe_http import fetch_bytes as safe_fetch_bytes
    from validate_target import validate_target

USER_AGENT = "WebactueelSEOChecker/1.4 (+https://github.com/Yolol100/seochecker)"


class PublicOnlyRedirectHandler(HTTPRedirectHandler):
    """Compatibility helper; safe_http performs the actual pinned redirect handling."""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_target(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _bounded_gzip_decompress(data: bytes, max_decompressed_bytes: int) -> bytes:
    with gzip.GzipFile(fileobj=io.BytesIO(data), mode="rb") as gz:
        out = gz.read(max_decompressed_bytes + 1)
    if len(out) > max_decompressed_bytes:
        raise ValueError(f"decompressed sitemap exceeds max_decompressed_bytes={max_decompressed_bytes}")
    return out


def fetch_sitemap_bytes(url: str, max_bytes: int, max_decompressed_bytes: int) -> bytes:
    validate_target(url)
    response = safe_fetch_bytes(url, timeout=20, max_bytes=max_bytes, headers={"User-Agent": USER_AGENT, "Accept": "application/xml,text/xml,*/*;q=0.5"})
    data = response.body
    content_type = response.headers.get("Content-Type", "").lower()
    content_encoding = response.headers.get("Content-Encoding", "").lower()
    if url.lower().endswith(".gz") or "gzip" in content_type or "gzip" in content_encoding:
        data = _bounded_gzip_decompress(data, max_decompressed_bytes)
    elif len(data) > max_decompressed_bytes:
        raise ValueError(f"sitemap exceeds max_decompressed_bytes={max_decompressed_bytes}")
    return data


def parse_locs(data: bytes) -> tuple[str, list[str]]:
    root = ET.fromstring(data)
    kind = root.tag.rsplit("}", 1)[-1].lower()
    if kind not in {"urlset", "sitemapindex"}:
        raise ValueError(f"unsupported sitemap root element: {kind}")
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


def collect(seeds: list[str], max_sitemaps: int, max_urls: int, max_bytes: int, max_decompressed_bytes: int) -> tuple[list[str], list[dict], bool]:
    queue = list(seeds)
    seen_maps = set()
    urls = []
    errors = []
    truncated = False
    while queue and len(seen_maps) < max_sitemaps and len(urls) < max_urls:
        sm = queue.pop(0)
        if sm in seen_maps:
            continue
        seen_maps.add(sm)
        try:
            kind, locs = parse_locs(fetch_sitemap_bytes(sm, max_bytes, max_decompressed_bytes))
            if kind == "sitemapindex":
                for loc in locs:
                    validate_target(loc)
                    if loc not in seen_maps and loc not in queue:
                        if len(seen_maps) + len(queue) >= max_sitemaps:
                            truncated = True
                            break
                        queue.append(loc)
            else:
                for loc in locs:
                    validate_target(loc)
                    if loc not in urls:
                        urls.append(loc)
                    if len(urls) >= max_urls:
                        truncated = True
                        break
        except Exception as exc:
            errors.append({"sitemap": sm, "error": str(exc)})
    if queue and len(seen_maps) >= max_sitemaps:
        truncated = True
    return urls, errors, truncated


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--input", required=True, help="batch JSON containing sitemap_candidates")
    ap.add_argument("--output", required=True, help="plain text URL list")
    ap.add_argument("--report", required=True, help="JSON extraction report")
    ap.add_argument("--max-sitemaps", type=int, default=100)
    ap.add_argument("--max-urls", type=int, default=10000)
    ap.add_argument("--max-bytes", type=int, default=20_000_000, help="max compressed/raw response bytes")
    ap.add_argument("--max-decompressed-bytes", type=int, default=50_000_000)
    args = ap.parse_args()
    if not 1 <= args.max_sitemaps <= 1000:
        raise ValueError("max-sitemaps must be between 1 and 1000")
    if not 1 <= args.max_urls <= 100000:
        raise ValueError("max-urls must be between 1 and 100000")
    if not 1 <= args.max_bytes <= 100_000_000 or not 1 <= args.max_decompressed_bytes <= 200_000_000:
        raise ValueError("sitemap byte limits outside supported safety bounds")
    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    seeds = sitemap_seeds(payload)
    urls, errors, truncated = collect(seeds, args.max_sitemaps, args.max_urls, args.max_bytes, args.max_decompressed_bytes)
    Path(args.output).write_text("".join(f"{u}\n" for u in urls), encoding="utf-8")
    report = {"schema_version": "1.1", "seed_count": len(seeds), "url_count": len(urls), "errors": errors, "truncated": truncated, "limits": {"max_sitemaps": args.max_sitemaps, "max_urls": args.max_urls, "max_response_bytes": args.max_bytes, "max_decompressed_bytes": args.max_decompressed_bytes}}
    Path(args.report).write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(args.report)
    return 0 if seeds else 2


if __name__ == "__main__":
    raise SystemExit(main())
