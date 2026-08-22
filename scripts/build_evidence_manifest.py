#!/usr/bin/env python3
import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path


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
        entry.update({"type": "directory", "file_count": len(files)})
        return entry
    entry.update({"type": "file", "bytes": path.stat().st_size, "sha256": sha256_file(path)})
    return entry


def build_manifest(workflow, target_url, artifacts, request_id="", source_set_version=""):
    return {
        "schema_version": "1.0",
        "repository": os.getenv("GITHUB_REPOSITORY", "Yolol100/seochecker"),
        "workflow": workflow,
        "target_url": target_url,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "request": {
            "request_id": request_id or None,
            "source_set_version": source_set_version or None,
        },
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
        ],
    }


def main():
    parser = argparse.ArgumentParser(description="Build a machine-readable SEO evidence manifest")
    parser.add_argument("--workflow", required=True)
    parser.add_argument("--target-url", required=True)
    parser.add_argument("--request-id", default="")
    parser.add_argument("--source-set-version", default="")
    parser.add_argument("--artifact", action="append", default=[])
    parser.add_argument("--output", default="reports/evidence-manifest.json")
    args = parser.parse_args()
    payload = build_manifest(args.workflow, args.target_url, args.artifact, args.request_id, args.source_set_version)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
