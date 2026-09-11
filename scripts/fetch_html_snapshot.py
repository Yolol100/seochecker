#!/usr/bin/env python3
"""Fetch one public HTML document through safe_http and store a local validation snapshot."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from .safe_http import fetch_bytes
except ImportError:
    try:
        from scripts.safe_http import fetch_bytes
    except ImportError:
        from safe_http import fetch_bytes


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("url")
    ap.add_argument("--output", required=True)
    ap.add_argument("--metadata", required=True)
    ap.add_argument("--max-bytes", type=int, default=8_000_000)
    args = ap.parse_args()
    response = fetch_bytes(
        args.url,
        timeout=25,
        max_bytes=args.max_bytes,
        headers={"User-Agent": "WebactueelSEOChecker/1.6", "Accept": "text/html,application/xhtml+xml,*/*;q=0.8"},
    )
    content_type = response.headers.get("Content-Type", "").lower()
    if content_type and "text/html" not in content_type and "application/xhtml+xml" not in content_type:
        raise ValueError(f"target did not return HTML: {content_type}")
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(bytes(response.body))
    meta = {
        "schema_version": "1.0",
        "requested_url": args.url,
        "final_url": response.url,
        "status": response.status,
        "connected_ip": response.connected_ip,
        "content_type": content_type,
        "bytes": out.stat().st_size,
    }
    Path(args.metadata).write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0 if 200 <= response.status < 300 else 1


if __name__ == "__main__":
    raise SystemExit(main())
