#!/usr/bin/env python3
"""Fail-closed compatibility and provenance check for a prior SEO Audit artifact."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

try:
    from .technical_evidence import url_key
except ImportError:
    try:
        from scripts.technical_evidence import url_key
    except ImportError:
        from technical_evidence import url_key

SUPPORTED_MANIFEST_SCHEMAS = {"1.2"}
SUPPORTED_FINDINGS_SCHEMAS = {"1.3"}
SUPPORTED_GRAPH_SCHEMAS = {"1.3"}


def sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def runtime_fingerprint(path: str) -> str:
    urls = sorted({url_key(x.strip()) for x in Path(path).read_text(encoding="utf-8").splitlines() if x.strip() and not x.lstrip().startswith("#")})
    return hashlib.sha256(("\n".join(urls) + "\n").encode("utf-8")).hexdigest()


def _artifact(manifest: dict, artifact_id: str) -> dict | None:
    for item in manifest.get("artifacts", []) or []:
        if isinstance(item, dict) and item.get("id") == artifact_id:
            return item
    return None


def _check_artifact_hash(errors: list[str], manifest: dict, artifact_id: str, path: str) -> None:
    item = _artifact(manifest, artifact_id)
    if not item or item.get("type") != "file" or not item.get("sha256"):
        errors.append(f"baseline manifest missing hash for {artifact_id}")
        return
    if not Path(path).is_file():
        errors.append(f"baseline file missing: {artifact_id}")
        return
    if sha256_file(path) != item["sha256"]:
        errors.append(f"baseline artifact hash mismatch: {artifact_id}")


def _check_json_schema(errors: list[str], label: str, path: str, supported: set[str]) -> str | None:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"baseline {label} is not valid JSON: {exc}")
        return None
    schema = str(payload.get("schema_version") or "") if isinstance(payload, dict) else ""
    if schema not in supported:
        errors.append(f"baseline {label} schema unsupported: {schema or 'missing'}")
    return schema or None


def validate(
    manifest: dict,
    target_url: str,
    crawl_scope: str,
    runtime_url_list: str,
    sitewide_max_urls: int,
    *,
    baseline_run_id: str = "",
    run_metadata: dict | None = None,
    findings_path: str = "",
    graph_path: str = "",
):
    errors: list[str] = []
    manifest_schema = str(manifest.get("schema_version") or "")
    if manifest_schema not in SUPPORTED_MANIFEST_SCHEMAS:
        errors.append(f"baseline manifest schema unsupported: {manifest_schema or 'missing'}")
    if manifest.get("repository") != "Yolol100/seochecker":
        errors.append("baseline repository mismatch")
    if manifest.get("workflow") != "SEO Audit":
        errors.append("baseline workflow mismatch")
    if url_key(manifest.get("target_url") or "") != url_key(target_url):
        errors.append("baseline target mismatch")
    scope = manifest.get("scope") if isinstance(manifest.get("scope"), dict) else {}
    if scope.get("crawl_scope") != crawl_scope:
        errors.append("baseline crawl_scope mismatch")
    current_fp = runtime_fingerprint(runtime_url_list)
    if scope.get("runtime_url_fingerprint_sha256") != current_fp:
        errors.append("baseline runtime URL scope mismatch")
    if crawl_scope == "sitewide" and int(scope.get("sitewide_max_urls") or 0) != int(sitewide_max_urls):
        errors.append("baseline sitewide max URL cap mismatch")
    github = manifest.get("github") if isinstance(manifest.get("github"), dict) else {}
    if baseline_run_id:
        if str(github.get("run_id") or "") != str(baseline_run_id):
            errors.append("baseline manifest run_id mismatch")
        if not github.get("sha"):
            errors.append("baseline manifest missing commit sha")
    if run_metadata is not None:
        database_id = str(run_metadata.get("databaseId") or run_metadata.get("database_id") or "")
        if baseline_run_id and database_id != str(baseline_run_id):
            errors.append("baseline GitHub run metadata id mismatch")
        if str(run_metadata.get("name") or "") != "SEO Audit":
            errors.append("baseline GitHub workflow name mismatch")
        if str(run_metadata.get("status") or "").lower() != "completed":
            errors.append("baseline GitHub run not completed")
        if str(run_metadata.get("conclusion") or "").lower() != "success":
            errors.append("baseline GitHub run not successful")
        if github.get("sha") and str(run_metadata.get("headSha") or run_metadata.get("head_sha") or "") != str(github.get("sha")):
            errors.append("baseline run commit sha mismatch")
    findings_schema = None
    graph_schema = None
    if findings_path:
        _check_artifact_hash(errors, manifest, "technical-findings", findings_path)
        if Path(findings_path).is_file():
            findings_schema = _check_json_schema(errors, "technical-findings", findings_path, SUPPORTED_FINDINGS_SCHEMAS)
    if graph_path:
        _check_artifact_hash(errors, manifest, "technical-graph", graph_path)
        if Path(graph_path).is_file():
            graph_schema = _check_json_schema(errors, "technical-graph", graph_path, SUPPORTED_GRAPH_SCHEMAS)
    return {
        "schema_version": "1.2",
        "compatible": not errors,
        "errors": errors,
        "current": {
            "target_url": url_key(target_url),
            "crawl_scope": crawl_scope,
            "runtime_url_fingerprint_sha256": current_fp,
            "sitewide_max_urls": sitewide_max_urls if crawl_scope == "sitewide" else None,
            "supported_manifest_schemas": sorted(SUPPORTED_MANIFEST_SCHEMAS),
            "supported_findings_schemas": sorted(SUPPORTED_FINDINGS_SCHEMAS),
            "supported_graph_schemas": sorted(SUPPORTED_GRAPH_SCHEMAS),
        },
        "baseline": {
            "run_id": github.get("run_id"),
            "sha": github.get("sha"),
            "manifest_schema": manifest_schema or None,
            "findings_schema": findings_schema,
            "graph_schema": graph_schema,
            "scope": scope,
        },
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--target-url", required=True)
    ap.add_argument("--crawl-scope", choices=["bounded", "sitewide"], required=True)
    ap.add_argument("--runtime-url-list", required=True)
    ap.add_argument("--sitewide-max-urls", type=int, default=500)
    ap.add_argument("--baseline-run-id", default="")
    ap.add_argument("--run-metadata")
    ap.add_argument("--findings")
    ap.add_argument("--graph")
    ap.add_argument("--output", required=True)
    args = ap.parse_args()
    result = validate(
        json.loads(Path(args.manifest).read_text(encoding="utf-8")),
        args.target_url,
        args.crawl_scope,
        args.runtime_url_list,
        args.sitewide_max_urls,
        baseline_run_id=args.baseline_run_id,
        run_metadata=json.loads(Path(args.run_metadata).read_text(encoding="utf-8")) if args.run_metadata else None,
        findings_path=args.findings or "",
        graph_path=args.graph or "",
    )
    Path(args.output).write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0 if result["compatible"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
