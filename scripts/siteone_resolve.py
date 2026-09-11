#!/usr/bin/env python3
"""Validate SiteOne trusted-target DNS without forcing HTTPS to a raw IP.

SiteOne 2.5.1 implements --resolve for its HTTP fetcher by replacing the URL host
with the supplied IP while only restoring the HTTP Host header. For HTTPS this
changes TLS/SNI/certificate semantics and can turn a healthy target into -1:CON.

Repository-owned HTTP remains IP-pinned by safe_http.py. SiteOne is a separate
third-party evidence layer and is allowed only for explicitly trusted targets.
This preflight validates every requested origin and writes explicit JSON evidence;
it intentionally emits no forced-IP arguments for SiteOne.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import urlsplit

try:
    from .safe_http import resolve_public_ips
except ImportError:
    try:
        from scripts.safe_http import resolve_public_ips
    except ImportError:
        from safe_http import resolve_public_ips


def _urls(path: str) -> list[str]:
    return [x.strip() for x in Path(path).read_text(encoding="utf-8").splitlines() if x.strip() and not x.lstrip().startswith("#")]


def validate_origins(urls: list[str]) -> list[dict]:
    seen: set[tuple[str, int, str]] = set()
    records: list[dict] = []
    for url in urls:
        parsed = urlsplit(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError(f"invalid HTTP(S) URL: {url}")
        if parsed.username or parsed.password:
            raise ValueError("credentials in SiteOne target URLs are not allowed")
        host = parsed.hostname.lower()
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        key = (host, port, parsed.scheme)
        if key in seen:
            continue
        seen.add(key)
        probe_url = f"{parsed.scheme}://{host}:{port}/"
        public_ips = resolve_public_ips(probe_url)
        records.append({
            "scheme": parsed.scheme,
            "host": host,
            "port": port,
            "public_ips": public_ips,
            "validation": "public_dns_only",
        })
    if not records:
        raise ValueError("no SiteOne target origins supplied")
    return records


def build_resolves(urls: list[str], include_www_peer: bool = True) -> list[str]:
    """Compatibility helper: validate origins and return no forced mappings."""
    del include_www_peer
    validate_origins(urls)
    return []


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--url-list", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()
    records = validate_origins(_urls(args.url_list))
    payload = {
        "schema_version": "1.0",
        "validated_origin_count": len(records),
        "origins": records,
        "forced_ip_arguments_emitted": false,
        "network_mode": "siteone_native_dns_tls",
        "reason": "SiteOne 2.5.1 forced-IP resolution changes HTTPS TLS/SNI semantics; advanced crawling is restricted to explicitly trusted targets.",
    }
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
