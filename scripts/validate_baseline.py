#!/usr/bin/env python3
"""Fail-closed compatibility check before comparing a prior SEO Audit artifact."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

try:
    from .technical_evidence import url_key
except ImportError:
    from technical_evidence import url_key


def runtime_fingerprint(path: str) -> str:
    urls = sorted({url_key(x.strip()) for x in Path(path).read_text(encoding="utf-8").splitlines() if x.strip() and not x.lstrip().startswith("#")})
    return hashlib.sha256(("\n".join(urls) + "\n").encode("utf-8")).hexdigest()


def validate(manifest: dict, target_url: str, crawl_scope: str, runtime_url_list: str, sitewide_max_urls: int):
    errors = []
    if manifest.get("repository") != "Yolol100/seochecker": errors.append("baseline repository mismatch")
    if manifest.get("workflow") != "SEO Audit": errors.append("baseline workflow mismatch")
    if url_key(manifest.get("target_url") or "") != url_key(target_url): errors.append("baseline target mismatch")
    scope = manifest.get("scope") if isinstance(manifest.get("scope"), dict) else {}
    if scope.get("crawl_scope") != crawl_scope: errors.append("baseline crawl_scope mismatch")
    current_fp = runtime_fingerprint(runtime_url_list)
    if scope.get("runtime_url_fingerprint_sha256") != current_fp: errors.append("baseline runtime URL scope mismatch")
    if crawl_scope == "sitewide" and int(scope.get("sitewide_max_urls") or 0) != int(sitewide_max_urls): errors.append("baseline sitewide max URL cap mismatch")
    return {"schema_version": "1.0", "compatible": not errors, "errors": errors, "current": {"target_url": url_key(target_url), "crawl_scope": crawl_scope, "runtime_url_fingerprint_sha256": current_fp, "sitewide_max_urls": sitewide_max_urls if crawl_scope == "sitewide" else None}, "baseline": scope}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--target-url", required=True)
    ap.add_argument("--crawl-scope", choices=["bounded", "sitewide"], required=True)
    ap.add_argument("--runtime-url-list", required=True)
    ap.add_argument("--sitewide-max-urls", type=int, default=500)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()
    result = validate(json.loads(Path(args.manifest).read_text(encoding="utf-8")), args.target_url, args.crawl_scope, args.runtime_url_list, args.sitewide_max_urls)
    Path(args.output).write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0 if result["compatible"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
