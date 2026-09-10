#!/usr/bin/env python3
"""Run the repository's stable HTTP technical check over a bounded public URL list."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from seo_basic_check import run
from validate_target import validate_target


def load_urls(path: str, max_urls: int) -> list[str]:
    values = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        value = line.strip()
        if not value or value.startswith("#"):
            continue
        validate_target(value)
        if value not in values:
            values.append(value)
        if len(values) > max_urls:
            raise ValueError(f"URL list exceeds max_urls={max_urls}")
    if not values:
        raise ValueError("URL list must contain at least one public HTTP(S) URL")
    return values


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--url-list", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--max-urls", type=int, default=500)
    args = ap.parse_args()
    if not 1 <= args.max_urls <= 5000:
        raise ValueError("max_urls must be between 1 and 5000")
    urls = load_urls(args.url_list, args.max_urls)
    records = [run(url) for url in urls]
    payload = {"schema_version": "1.0", "url_count": len(urls), "records": records}
    out = Path(args.output); out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
