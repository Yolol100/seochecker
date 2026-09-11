#!/usr/bin/env python3
"""Build deterministic SiteOne --resolve arguments from public runtime URLs."""
from __future__ import annotations

import argparse
import ipaddress
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


def _preferred_ip(ips: list[str]) -> str:
    if not ips:
        raise ValueError("no public IPs available")
    ipv4 = [ip for ip in ips if ipaddress.ip_address(ip).version == 4]
    return (ipv4 or ips)[0]


def build_resolves(urls: list[str], include_www_peer: bool = True) -> list[str]:
    targets: dict[tuple[str, int, str], None] = {}
    for url in urls:
        parsed = urlsplit(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError(f"invalid HTTP(S) URL: {url}")
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        targets[(parsed.hostname.lower(), port, parsed.scheme)] = None
        if include_www_peer:
            peer = parsed.hostname[4:] if parsed.hostname.lower().startswith("www.") else f"www.{parsed.hostname}"
            targets[(peer.lower(), port, parsed.scheme)] = None
    args: list[str] = []
    for host, port, scheme in sorted(targets):
        try:
            ip = _preferred_ip(resolve_public_ips(f"{scheme}://{host}:{port}/"))
        except ValueError:
            # The www/non-www peer is optional. A requested host is not.
            requested = any((urlsplit(u).hostname or "").lower() == host and (urlsplit(u).port or (443 if urlsplit(u).scheme == "https" else 80)) == port for u in urls)
            if requested:
                raise
            continue
        args.append(f"--resolve={host}:{port}:{ip}")
    return args


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--url-list", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()
    values = build_resolves(_urls(args.url_list))
    if not values:
        raise ValueError("no SiteOne resolve mappings generated")
    Path(args.output).write_text("".join(v + "\n" for v in values), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
