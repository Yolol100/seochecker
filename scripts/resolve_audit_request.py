#!/usr/bin/env python3
"""Resolve workflow_dispatch or requests/audit.json into strict GitHub Actions outputs."""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

ID_RE = re.compile(r"^[A-Za-z0-9._-]{3,80}$")
TEXT_FIELDS = ("for", "task", "why", "trigger_when", "do_not_trigger_when", "requested_by")


def public_url(value: str) -> str:
    raw = str(value or "").strip()
    p = urlsplit(raw)
    if p.scheme not in {"http", "https"} or not p.hostname:
        raise ValueError("URL must be HTTP(S)")
    if p.username or p.password:
        raise ValueError("URL credentials are forbidden")
    return urlunsplit((p.scheme, p.netloc, p.path or "/", p.query, ""))


def boolean(value, default=False) -> bool:
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"true", "1", "yes"}: return True
    if text in {"false", "0", "no"}: return False
    raise ValueError(f"invalid boolean: {value}")


def scope_value(value) -> str:
    scope = str(value or "bounded").strip().lower()
    if scope not in {"bounded", "sitewide"}:
        raise ValueError("crawl_scope must be bounded or sitewide")
    return scope


def max_value(value) -> int:
    try: n = int(str(value or "500"))
    except ValueError as exc: raise ValueError("sitewide_max_urls must be 1..5000") from exc
    if not 1 <= n <= 5000: raise ValueError("sitewide_max_urls must be 1..5000")
    return n


def baseline_value(value) -> str:
    text = str(value or "").strip()
    if text and not text.isdigit(): raise ValueError("baseline_run_id must be numeric")
    return text


def _safe_text(value) -> bool:
    return isinstance(value, str) and bool(value.strip()) and "\n" not in value and "\r" not in value


def _dedupe(urls: list[str]) -> list[str]:
    return list(dict.fromkeys(urls))


def resolve(event_name: str, env: dict[str, str], request_path: str) -> dict[str, str]:
    run = False; request_id = "none"; target = ""; source_version = ""; urls: list[str] = []
    scope = "bounded"; sitewide_max = 500; render_js = False; trusted = False; baseline = ""; fail_regression = True
    if event_name == "workflow_dispatch":
        target = public_url(env.get("DISPATCH_URL", "")); urls = [target]
        for raw in env.get("DISPATCH_URL_LIST", "").splitlines():
            if raw.strip(): urls.append(public_url(raw))
        scope = scope_value(env.get("DISPATCH_CRAWL_SCOPE")); sitewide_max = max_value(env.get("DISPATCH_SITEWIDE_MAX_URLS"))
        render_js = boolean(env.get("DISPATCH_RENDER_JS")); trusted = boolean(env.get("DISPATCH_TRUSTED_RENDER_TARGET"))
        baseline = baseline_value(env.get("DISPATCH_BASELINE_RUN_ID")); fail_regression = boolean(env.get("DISPATCH_FAIL_ON_REGRESSION"), True)
        source_version = str(env.get("DISPATCH_SOURCE_SET_VERSION", "")).strip(); request_id = f"dispatch-{env.get('GITHUB_RUN_ID','unknown')}"; run = True
    elif Path(request_path).is_file():
        req = json.loads(Path(request_path).read_text(encoding="utf-8"))
        if req.get("enabled") is True:
            if not ID_RE.fullmatch(str(req.get("request_id") or "")): raise ValueError("invalid request_id")
            if req.get("owner") != "seo" or req.get("project_id") != "project-seo": raise ValueError("request owner/project mismatch")
            for key in TEXT_FIELDS:
                if not _safe_text(req.get(key)): raise ValueError(f"missing or unsafe {key}")
            source = req.get("source_context") if isinstance(req.get("source_context"), dict) else {}
            if source.get("project_id") != "project-seo" or not _safe_text(source.get("source_set_version")): raise ValueError("invalid source_context")
            target = public_url(req.get("url", "")); urls = [target] + [public_url(x) for x in (req.get("urls") or [])]
            scope = scope_value(req.get("crawl_scope")); sitewide_max = max_value(req.get("sitewide_max_urls")); render_js = req.get("render_js") is True; trusted = req.get("trusted_render_target") is True
            baseline = baseline_value(req.get("baseline_run_id")); fail_regression = req.get("fail_on_regression") is not False; source_version = source["source_set_version"].strip(); request_id = req["request_id"]; run = True
    urls = _dedupe(urls)
    if len(urls) > 500: raise ValueError(f"runtime URL list exceeds hard cap 500 (got {len(urls)})")
    if render_js and not trusted: raise ValueError("render_js requires trusted_render_target=true")
    if scope == "sitewide" and not trusted: raise ValueError("sitewide scope requires trusted_render_target=true because SiteOne performs autonomous discovery")
    return {
        "run": str(run).lower(), "request_id": request_id, "target_url": target, "source_set_version": source_version,
        "url_list_b64": base64.b64encode("\n".join(urls).encode()).decode(), "crawl_scope": scope, "sitewide_max_urls": str(sitewide_max),
        "render_js": str(render_js).lower(), "trusted_render_target": str(trusted).lower(), "baseline_run_id": baseline, "fail_on_regression": str(fail_regression).lower(),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__); ap.add_argument("--event-name", required=True); ap.add_argument("--request", default="requests/audit.json"); ap.add_argument("--output", default=os.getenv("GITHUB_OUTPUT", "")); args = ap.parse_args()
    result = resolve(args.event_name, dict(os.environ), args.request)
    if not args.output: print(json.dumps(result, indent=2)); return 0
    with open(args.output, "a", encoding="utf-8") as handle:
        for key, value in result.items(): handle.write(f"{key}={value}\n")
    return 0

if __name__ == "__main__": raise SystemExit(main())
