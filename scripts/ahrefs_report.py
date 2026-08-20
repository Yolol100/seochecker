#!/usr/bin/env python3
import argparse
import json
import os
import re
import time
from datetime import date, timedelta
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

BASE = "https://api.ahrefs.com/v3/site-explorer"
RETRYABLE_HTTP_STATUS = {429, 500, 502, 503, 504}
DEFAULT_ATTEMPTS = 3
DEFAULT_RETRY_BASE_SECONDS = 1.0
MAX_RETRY_AFTER_SECONDS = 30.0
SUSPICIOUS_ANCHOR_PATTERNS = [
    r"seoexpress",
    r"\bpbn\b",
    r"buy backlinks?",
    r"backlinks?",
    r"guest posts?",
    r"rank first",
    r"first page google",
    r"dr/da/tf",
    r"link building",
    r"seo partner",
]


def _retry_delay(headers, attempt, base_seconds):
    retry_after = None
    if headers is not None:
        try:
            retry_after = headers.get("Retry-After")
        except AttributeError:
            retry_after = None
    if retry_after:
        try:
            return min(max(float(retry_after), 0.0), MAX_RETRY_AFTER_SECONDS)
        except (TypeError, ValueError):
            pass
    return base_seconds * (2 ** max(attempt - 1, 0))


def api_get(
    endpoint,
    api_key,
    params,
    timeout=45,
    attempts=DEFAULT_ATTEMPTS,
    retry_base_seconds=DEFAULT_RETRY_BASE_SECONDS,
    sleeper=None,
):
    url = f"{BASE}/{endpoint}?{urlencode(params)}"
    req = Request(url, headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"})
    sleeper = sleeper or time.sleep
    attempts = max(int(attempts), 1)

    for attempt in range(1, attempts + 1):
        try:
            with urlopen(req, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8", errors="replace"))
        except HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            if exc.code in RETRYABLE_HTTP_STATUS and attempt < attempts:
                sleeper(_retry_delay(exc.headers, attempt, retry_base_seconds))
                continue
            raise RuntimeError(f"Ahrefs HTTP {exc.code}: {raw[:1200]}") from exc
        except (URLError, TimeoutError, OSError) as exc:
            if attempt < attempts:
                sleeper(_retry_delay(None, attempt, retry_base_seconds))
                continue
            raise RuntimeError(str(exc)) from exc

    raise RuntimeError("Ahrefs API request failed after retries")


def is_suspicious_anchor(anchor):
    text = (anchor or "").lower()
    return any(re.search(pattern, text, flags=re.I) for pattern in SUSPICIOUS_ANCHOR_PATTERNS)


def summarize_history(history):
    rows = sorted((history or []), key=lambda x: x.get("date", ""))
    if not rows:
        return {"first": None, "last": None, "growth": None, "growth_pct": None, "largest_daily_increase": None}
    first = rows[0]
    last = rows[-1]
    first_value = int(first.get("refdomains", 0) or 0)
    last_value = int(last.get("refdomains", 0) or 0)
    growth = last_value - first_value
    growth_pct = round(growth / first_value * 100, 2) if first_value else None
    largest = None
    for prev, cur in zip(rows, rows[1:]):
        inc = int(cur.get("refdomains", 0) or 0) - int(prev.get("refdomains", 0) or 0)
        candidate = {"date": cur.get("date"), "increase": inc, "from": prev.get("refdomains"), "to": cur.get("refdomains")}
        if largest is None or inc > largest["increase"]:
            largest = candidate
    return {
        "first": first,
        "last": last,
        "growth": growth,
        "growth_pct": growth_pct,
        "largest_daily_increase": largest,
    }


def summarize_anchors(anchors):
    suspicious = [a for a in (anchors or []) if is_suspicious_anchor(a.get("anchor")) or a.get("is_spam") is True]
    return {
        "sample_size": len(anchors or []),
        "suspicious_anchor_rows": len(suspicious),
        "suspicious_refdomains_sum": sum(int(a.get("refdomains", 0) or 0) for a in suspicious),
        "suspicious_dofollow_links_sum": sum(int(a.get("dofollow_links", 0) or 0) for a in suspicious),
        "examples": suspicious[:20],
    }


def summarize_refdomains(refdomains):
    rows = refdomains or []
    spam = [r for r in rows if r.get("is_spam") is True]
    zero_traffic = [r for r in rows if float(r.get("traffic_domain", 0) or 0) <= 0]
    return {
        "sample_size": len(rows),
        "ahrefs_spam_sample_count": len(spam),
        "ahrefs_spam_sample_pct": round(len(spam) / len(rows) * 100, 2) if rows else None,
        "zero_traffic_sample_count": len(zero_traffic),
        "examples": spam[:20],
    }


def build_report(target, days, api_key):
    if not api_key:
        return {
            "status": "not_configured",
            "reason": "AHREFS_API_KEY ontbreekt",
            "target": target,
            "required_secret": "AHREFS_API_KEY",
        }
    end = date.today()
    start = end - timedelta(days=max(days, 2) - 1)
    common = {"target": target, "mode": "subdomains", "protocol": "both", "output": "json"}
    history = api_get("refdomains-history", api_key, {**common, "date_from": start.isoformat(), "date_to": end.isoformat(), "history_grouping": "daily"}).get("refdomains", [])
    stats = api_get("backlinks-stats", api_key, {**common, "date": end.isoformat()}).get("metrics", {})
    anchors = api_get(
        "anchors",
        api_key,
        {
            **common,
            "limit": 100,
            "order_by": "refdomains:desc",
            "select": "anchor,refdomains,refpages,links_to_target,dofollow_links,first_seen,is_spam",
        },
    ).get("anchors", [])
    refdomains = api_get(
        "refdomains",
        api_key,
        {
            **common,
            "limit": 100,
            "order_by": "first_seen:desc",
            "select": "domain,domain_rating,first_seen,is_spam,links_to_target,dofollow_links,traffic_domain",
        },
    ).get("refdomains", [])
    return {
        "status": "ok",
        "target": target,
        "date_range": {"start": start.isoformat(), "end": end.isoformat()},
        "backlink_stats": stats,
        "refdomains_history_summary": summarize_history(history),
        "refdomains_history": history,
        "anchor_summary": summarize_anchors(anchors),
        "anchors_sample": anchors,
        "refdomains_sample_summary": summarize_refdomains(refdomains),
        "refdomains_sample": refdomains,
        "limitations": [
            "Ahrefs-data is third-party diagnostiek en bewijst geen Google-penalty.",
            "Ahrefs first_seen betekent wanneer Ahrefs een backlink voor het eerst vond, niet noodzakelijk wanneer die link is aangemaakt.",
            "is_spam is een Ahrefs-classificatie, niet Google's oordeel.",
            "Anchor- en referring-domainlijsten zijn beperkt tot een compatibele sample van maximaal 100 rijen per endpoint.",
            "Tijdelijke HTTP 429/5xx- en netwerkfouten worden maximaal drie keer geprobeerd met oplopende wachttijd.",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description="Ahrefs backlink diagnostic report")
    parser.add_argument("--target", required=True)
    parser.add_argument("--days", type=int, default=180)
    parser.add_argument("--output", default="reports/ahrefs-report.json")
    args = parser.parse_args()
    api_key = os.getenv("AHREFS_API_KEY", "").strip()
    try:
        result = build_report(args.target, args.days, api_key)
    except Exception as exc:
        result = {"status": "error", "error": str(exc), "target": args.target}
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
