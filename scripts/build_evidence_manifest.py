#!/usr/bin/env python3
import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

try:
    from .technical_evidence import url_key
except ImportError:
    from technical_evidence import url_key


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def artifact_entry(spec):
    if "=" not in spec:
        raise ValueError(f"ongeldige artifact-specificatie: {spec}")
    artifact_id, raw_path = spec.split("=", 1)
    artifact_id = artifact_id.strip()
    raw_path = raw_path.strip()
    if not artifact_id or not raw_path:
        raise ValueError(f"ongeldige artifact-specificatie: {spec}")
    path = Path(raw_path)
    entry = {"id": artifact_id, "path": str(path), "exists": path.exists()}
    if not path.exists():
        entry["type"] = "missing"
        return entry
    if path.is_dir():
        files = sorted(p for p in path.rglob("*") if p.is_file())
        digest = hashlib.sha256()
        for file in files:
            digest.update(str(file.relative_to(path)).encode("utf-8") + b"\0")
            digest.update(sha256_file(file).encode("ascii") + b"\n")
        entry.update({"type": "directory", "file_count": len(files), "tree_sha256": digest.hexdigest()})
        return entry
    entry.update({"type": "file", "bytes": path.stat().st_size, "sha256": sha256_file(path)})
    return entry


def _runtime_scope(path: str | None):
    if not path or not Path(path).is_file():
        return {"runtime_url_count": 0, "runtime_url_fingerprint_sha256": None}
    urls = sorted({url_key(x.strip()) for x in Path(path).read_text(encoding="utf-8").splitlines() if x.strip() and not x.lstrip().startswith("#")})
    digest = hashlib.sha256(("\n".join(urls) + "\n").encode("utf-8")).hexdigest()
    return {"runtime_url_count": len(urls), "runtime_url_fingerprint_sha256": digest}


def build_manifest(workflow, target_url, artifacts, request_id="", source_set_version="", crawl_scope="bounded", runtime_url_list="", sitewide_max_urls=0, baseline_run_id="", scope_report=""):
    scope = {"crawl_scope": crawl_scope, **_runtime_scope(runtime_url_list)}
    if crawl_scope == "sitewide":
        scope["sitewide_max_urls"] = int(sitewide_max_urls or 0)
    if scope_report and Path(scope_report).is_file():
        try:
            report = json.loads(Path(scope_report).read_text(encoding="utf-8"))
            scope["scope_complete"] = report.get("scope_complete")
            scope["crawl_limit_reached"] = report.get("crawl_limit_reached")
            scope["effective_url_count"] = report.get("effective_url_count")
            # Backward-compatible aliases are kept only for sitewide scope.
            if crawl_scope == "sitewide":
                scope["sitewide_scope_complete"] = report.get("scope_complete")
                scope["sitewide_crawl_limit_reached"] = report.get("crawl_limit_reached")
        except Exception as exc:
            scope["scope_report_error"] = str(exc)
    return {
        "schema_version": "1.2",
        "repository": os.getenv("GITHUB_REPOSITORY", "Yolol100/seochecker"),
        "workflow": workflow,
        "target_url": target_url,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "request": {
            "request_id": request_id or None,
            "source_set_version": source_set_version or None,
            "baseline_run_id": str(baseline_run_id) if baseline_run_id else None,
        },
        "scope": scope,
        "github": {
            "run_id": os.getenv("GITHUB_RUN_ID") or None,
            "run_attempt": os.getenv("GITHUB_RUN_ATTEMPT") or None,
            "sha": os.getenv("GITHUB_SHA") or None,
            "ref": os.getenv("GITHUB_REF") or None,
        },
        "artifacts": [artifact_entry(spec) for spec in artifacts],
        "evidence_boundaries": [
            "Workflow completion plus artifact/log evidence is required before claiming the audit executed.",
            "Source-set context identifies the policy snapshot used by the caller; it does not make repository output project truth.",
            "Lighthouse is labdata; Search Console is authoritative for owned Google Search performance and index status.",
            "Bounded scope verifies only the explicit runtime URL set. Site-wide scope is complete only when scope.scope_complete=true.",
            "Rendered SiteOne JSON does not reliably export every rendered head relation; use dedicated browser DOM evidence when those fields can change acceptance.",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description="Build a machine-readable SEO evidence manifest")
    parser.add_argument("--workflow", required=True)
    parser.add_argument("--target-url", required=True)
    parser.add_argument("--request-id", default="")
    parser.add_argument("--source-set-version", default="")
    parser.add_argument("--crawl-scope", choices=["bounded", "sitewide"], default="bounded")
    parser.add_argument("--runtime-url-list", default="")
    parser.add_argument("--sitewide-max-urls", type=int, default=0)
    parser.add_argument("--baseline-run-id", default="")
    parser.add_argument("--scope-report", default="")
    parser.add_argument("--artifact", action="append", default=[])
    parser.add_argument("--output", default="reports/evidence-manifest.json")
    args = parser.parse_args()
    payload = build_manifest(
        args.workflow,
        args.target_url,
        args.artifact,
        args.request_id,
        args.source_set_version,
        args.crawl_scope,
        args.runtime_url_list,
        args.sitewide_max_urls,
        args.baseline_run_id,
        args.scope_report,
    )
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
