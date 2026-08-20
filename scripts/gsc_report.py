#!/usr/bin/env python3
import argparse
import json
import os
from datetime import date, timedelta
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, quote
from urllib.request import Request, urlopen

TOKEN_URL = "https://oauth2.googleapis.com/token"
SEARCH_ANALYTICS_BASE = "https://www.googleapis.com/webmasters/v3/sites/{site}/searchAnalytics/query"
URL_INSPECTION_URL = "https://searchconsole.googleapis.com/v1/urlInspection/index:inspect"


def request_json(url, method="GET", headers=None, payload=None, form=None, timeout=30):
    body = None
    hdrs = dict(headers or {})
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        hdrs.setdefault("Content-Type", "application/json")
    elif form is not None:
        body = urlencode(form).encode("utf-8")
        hdrs.setdefault("Content-Type", "application/x-www-form-urlencoded")
    req = Request(url, data=body, headers=hdrs, method=method)
    try:
        with urlopen(req, timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
            return json.loads(raw) if raw else {}
    except HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {raw[:1000]}") from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise RuntimeError(str(exc)) from exc


def get_access_token(client_id, client_secret, refresh_token):
    data = request_json(
        TOKEN_URL,
        method="POST",
        form={
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        },
    )
    token = data.get("access_token")
    if not token:
        raise RuntimeError("Google OAuth response bevat geen access_token")
    return token


def search_analytics(token, site_url, start_date, end_date, dimensions, filters=None, row_limit=25000):
    site = quote(site_url, safe="")
    payload = {
        "startDate": start_date,
        "endDate": end_date,
        "dimensions": dimensions,
        "type": "web",
        "dataState": "final",
        "rowLimit": row_limit,
    }
    if filters:
        payload["dimensionFilterGroups"] = [{"groupType": "and", "filters": filters}]
    return request_json(
        SEARCH_ANALYTICS_BASE.format(site=site),
        method="POST",
        headers={"Authorization": f"Bearer {token}"},
        payload=payload,
    )


def inspect_url(token, site_url, inspection_url, language_code):
    return request_json(
        URL_INSPECTION_URL,
        method="POST",
        headers={"Authorization": f"Bearer {token}"},
        payload={
            "inspectionUrl": inspection_url,
            "siteUrl": site_url,
            "languageCode": language_code,
        },
    )


def rows_by_date(rows):
    out = {}
    for row in rows or []:
        keys = row.get("keys") or []
        if not keys:
            continue
        out[keys[0]] = {
            "clicks": float(row.get("clicks", 0) or 0),
            "impressions": float(row.get("impressions", 0) or 0),
            "ctr": float(row.get("ctr", 0) or 0),
            "position": float(row.get("position", 0) or 0),
        }
    return out


def weighted_position(records):
    total_impressions = sum(r["impressions"] for r in records)
    if total_impressions <= 0:
        return None
    return sum(r["position"] * r["impressions"] for r in records) / total_impressions


def summarize_records(records):
    clicks = sum(r["clicks"] for r in records)
    impressions = sum(r["impressions"] for r in records)
    position = weighted_position(records)
    return {
        "clicks": round(clicks, 2),
        "impressions": round(impressions, 2),
        "ctr": round(clicks / impressions, 6) if impressions else None,
        "position": round(position, 3) if position is not None else None,
    }


def pct_change(current, previous):
    if previous in (0, None):
        return None
    return round(((current - previous) / previous) * 100, 2)


def period_comparison(daily_rows, end_date, period_days=28):
    by_date = rows_by_date(daily_rows)
    end = date.fromisoformat(end_date)
    current_dates = [end - timedelta(days=i) for i in range(period_days - 1, -1, -1)]
    previous_end = current_dates[0] - timedelta(days=1)
    previous_dates = [previous_end - timedelta(days=i) for i in range(period_days - 1, -1, -1)]
    zero = {"clicks": 0.0, "impressions": 0.0, "ctr": 0.0, "position": 0.0}
    current = [by_date.get(d.isoformat(), zero) for d in current_dates]
    previous = [by_date.get(d.isoformat(), zero) for d in previous_dates]
    current_summary = summarize_records(current)
    previous_summary = summarize_records(previous)
    return {
        "period_days": period_days,
        "current": current_summary,
        "previous": previous_summary,
        "clicks_change_pct": pct_change(current_summary["clicks"], previous_summary["clicks"]),
        "impressions_change_pct": pct_change(current_summary["impressions"], previous_summary["impressions"]),
    }


def largest_weekly_impression_drop(daily_rows, start_date, end_date):
    by_date = rows_by_date(daily_rows)
    start = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date)
    days = []
    cursor = start
    while cursor <= end:
        days.append((cursor, by_date.get(cursor.isoformat(), {}).get("impressions", 0.0)))
        cursor += timedelta(days=1)
    best = None
    for idx in range(13, len(days)):
        previous = sum(v for _, v in days[idx - 13:idx - 6])
        current = sum(v for _, v in days[idx - 6:idx + 1])
        if previous <= 0:
            continue
        change = ((current - previous) / previous) * 100
        candidate = {
            "week_ending": days[idx][0].isoformat(),
            "previous_7d_impressions": round(previous, 2),
            "current_7d_impressions": round(current, 2),
            "change_pct": round(change, 2),
        }
        if best is None or candidate["change_pct"] < best["change_pct"]:
            best = candidate
    return best


def compact_rows(rows, key_name, limit=100):
    out = []
    for row in (rows or [])[:limit]:
        keys = row.get("keys") or []
        out.append({
            key_name: keys[0] if keys else None,
            "clicks": row.get("clicks", 0),
            "impressions": row.get("impressions", 0),
            "ctr": row.get("ctr", 0),
            "position": row.get("position", 0),
        })
    return out


def build_report(site_url, inspection_url, country_code, language_code, days, credentials):
    if not all(credentials.values()):
        return {
            "status": "not_configured",
            "reason": "GSC OAuth secrets ontbreken",
            "required_secrets": ["GSC_CLIENT_ID", "GSC_CLIENT_SECRET", "GSC_REFRESH_TOKEN"],
            "site_url": site_url,
            "inspection_url": inspection_url,
        }
    if not site_url:
        return {"status": "not_configured", "reason": "gsc_property ontbreekt", "inspection_url": inspection_url}

    end = date.today() - timedelta(days=2)
    start = end - timedelta(days=max(days, 56) - 1)
    token = get_access_token(credentials["client_id"], credentials["client_secret"], credentials["refresh_token"])
    all_daily = search_analytics(token, site_url, start.isoformat(), end.isoformat(), ["date"]).get("rows", [])
    country_filter = [{"dimension": "country", "operator": "equals", "expression": country_code.upper()}] if country_code else None
    country_daily = search_analytics(token, site_url, start.isoformat(), end.isoformat(), ["date"], country_filter).get("rows", [])
    top_queries = search_analytics(token, site_url, start.isoformat(), end.isoformat(), ["query"], country_filter, 250).get("rows", [])
    top_pages = search_analytics(token, site_url, start.isoformat(), end.isoformat(), ["page"], country_filter, 250).get("rows", [])
    inspection = inspect_url(token, site_url, inspection_url, language_code) if inspection_url else {}

    return {
        "status": "ok",
        "site_url": site_url,
        "inspection_url": inspection_url,
        "country_code": country_code.upper() if country_code else None,
        "date_range": {"start": start.isoformat(), "end": end.isoformat()},
        "all_search": {
            "period_comparison": period_comparison(all_daily, end.isoformat()),
            "largest_weekly_impression_drop": largest_weekly_impression_drop(all_daily, start.isoformat(), end.isoformat()),
            "daily": all_daily,
        },
        "target_country": {
            "period_comparison": period_comparison(country_daily, end.isoformat()),
            "largest_weekly_impression_drop": largest_weekly_impression_drop(country_daily, start.isoformat(), end.isoformat()),
            "daily": country_daily,
            "top_queries": compact_rows(top_queries, "query"),
            "top_pages": compact_rows(top_pages, "page"),
        },
        "url_inspection": inspection,
        "limitations": [
            "Search Analytics kan door interne limieten niet alle rijen teruggeven; toplijsten zijn geen volledige export.",
            "URL Inspection API toont de versie/status in Google's index en voert geen live URL-test uit.",
            "Manual Actions en Security Issues moeten apart in Search Console worden gecontroleerd.",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description="Google Search Console diagnostic report")
    parser.add_argument("--site-url", default="")
    parser.add_argument("--inspection-url", required=True)
    parser.add_argument("--country-code", default="DEU")
    parser.add_argument("--language-code", default="de-DE")
    parser.add_argument("--days", type=int, default=180)
    parser.add_argument("--output", default="reports/gsc-report.json")
    args = parser.parse_args()

    creds = {
        "client_id": os.getenv("GSC_CLIENT_ID", "").strip(),
        "client_secret": os.getenv("GSC_CLIENT_SECRET", "").strip(),
        "refresh_token": os.getenv("GSC_REFRESH_TOKEN", "").strip(),
    }
    try:
        result = build_report(args.site_url.strip(), args.inspection_url, args.country_code, args.language_code, args.days, creds)
    except Exception as exc:
        result = {"status": "error", "error": str(exc), "site_url": args.site_url, "inspection_url": args.inspection_url}
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
