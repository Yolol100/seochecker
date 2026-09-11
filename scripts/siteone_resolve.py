#!/usr/bin/env python3
"""Validate SiteOne trusted-target DNS without forcing HTTPS to a raw IP.

SiteOne 2.5.1 implements --resolve for its HTTP fetcher by replacing the URL host
with the supplied IP while only restoring the HTTP Host header. For HTTPS this
changes TLS/SNI/certificate semantics and can turn a healthy target into -1:CON.

Repository-owned HTTP remains IP-pinned by safe_http.py. SiteOne is a separate
third-party evidence layer and is allowed only for explicitly trusted targets,
so this compatibility preflight validates that every requested host resolves
only to public addresses and intentionally emits no --resolve arguments.
"""
from __future__ import annotations

import argparse
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


def build_resolves(urls: list[str], include_www_peer: bool = True) -> list[str]:
    """Validate requested origins and return no forced mappings for SiteOne 2.5.1.

    The function name is retained for compatibility with existing callers/tests.
    `include_www_peer` is retained as a compatibility argument but optional peer
    hosts are deliberately not introduced into the trust surface.
    """
    del include_www_peer
    seen: set[tuple[str, int, str]] = set()
    for url in urls:
        parsed = urlsplit(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError(f"invalid HTTP(S) URL: {url}")
        if parsed.username or parsed.password:
            raise ValueError("credentials in SiteOne target URLs are not allowed")
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        key = (parsed.hostname.lower(), port, parsed.scheme)
        if key in seen:
            continue
        seen.add(key)
        resolve_public_ips(f"{parsed.scheme}://{parsed.hostname}:{port}/")
    if not seen:
        raise ValueError("no SiteOne target origins supplied")
    return []


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--url-list", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()
    values = build_resolves(_urls(args.url_list))
    # An empty file is intentional: it proves preflight ran while ensuring the
    # SiteOne command receives no TLS-breaking --resolve arguments.
    Path(args.output).write_text("".join(v + "\n" for v in values), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
