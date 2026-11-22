"""Private technical SEO facts for a completed, owner-requested lead batch.

No Ahrefs, pricing, outreach, client lists in GitHub, or sales conclusions.
Called only after Leadscanner verified its complete immutable run cohort.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import os
import re
from urllib.parse import quote, urlsplit
from urllib.robotparser import RobotFileParser

TAB = "OpportunityAudits"
CHECKER = "seo-technical-v1"
HEADERS = ("run_id", "record_key", "source_sha256", "checker", "checked_at",
           "status", "findings_json")
BOT = "WebactueelSEOChecker"
MAX_GOAL = 1000
MAX_WORKERS = 4
ALLOWED_STATUS = frozenset({"BEVESTIGD", "NIET_VERIFIEERBAAR", "NOT_RUN"})


def select_verified(history, evidence, run_id, goal):
    """Join by privately verified identity; no raw lead data in public output."""
    from lead_audit_handoff import _digest, verify_private_batch
    if verify_private_batch(history, evidence, run_id, goal) != goal:
        raise RuntimeError("source_batch_incomplete")
    official = {r[0]: r for r in evidence[1:] if r[1] == "Approved"}
    records = []
    for row in history[1:]:
        if row[0] != run_id:
            continue
        company, website, email = row[1:4]
        key = "Approved:" + _digest([company, website, email])[:24]
        proof = official[key]
        records.append({"record_key": key, "source_sha256": proof[3],
                        "url": website})
    return sorted(records, key=lambda r: r["record_key"])


def inspect_site(url, *, fetch=None, analyze=None):
    """Bounded, robots-respecting, SSRF-pinned public HTML proof."""
    if fetch is None:
        from safe_http import fetch_text
        fetch = fetch_text
    if analyze is None:
        from seo_basic_check import analyze_html
        analyze = analyze_html
    try:
        parsed = urlsplit(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            return "NIET_VERIFIEERBAAR", {"reason": "invalid_origin"}
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            return "NIET_VERIFIEERBAAR", {"reason": "invalid_origin"}
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        robots = fetch(robots_url, timeout=12, max_bytes=100_000,
                       headers={"User-Agent": BOT})
        if urlsplit(robots.url).hostname != parsed.hostname:
            return "NIET_VERIFIEERBAAR", {"reason": "robots_cross_origin"}
        if robots.status == 200:
            robot_parser = RobotFileParser()
            robot_parser.parse(str(robots.body).splitlines())
            if not robot_parser.can_fetch(BOT, url):
                return "NOT_RUN", {"reason": "robots_disallowed"}
        elif robots.status != 404:
            return "NIET_VERIFIEERBAAR", {"reason": "robots_unavailable"}
        page = fetch(url, timeout=16, max_bytes=2_000_000, allow_truncate=True,
                     headers={"User-Agent": BOT, "Accept": "text/html",
                              "Accept-Encoding": "identity"})
        final = urlsplit(page.url)
        if not (page.status == 200 and final.hostname and
                final.hostname.removeprefix("www.") == parsed.hostname.removeprefix("www.")
                and "text/html" in (page.headers.get("Content-Type", "").lower())):
            return "NIET_VERIFIEERBAAR", {"reason": "site_not_same_origin_html"}
        facts = analyze(page.body, page.url)
        blockers = list(facts.get("indexability_blockers") or [])
        xr = page.headers.get("X-Robots-Tag", "")
        if "noindex" in xr.lower():
            blockers.append("X-Robots-Tag bevat noindex")
        return "BEVESTIGD", {
            "checked_url": page.url,
            "http_status": page.status,
            "title_present": bool(facts.get("title")),
            "meta_description_present": bool(facts.get("meta_descriptions")),
            "h1_count": int(facts.get("h1_count") or 0),
            "canonical_present": bool(facts.get("canonical")),
            "structured_data_types": list(facts.get("jsonld_types") or [])[:12],
            "indexability_blockers": blockers[:12],
            "technical_warnings": list(facts.get("warnings") or [])[:12],
            "html_truncated": bool(page.truncated),
            "rendered_ux": "NOT_RUN",
            "booking_conversion": "NOT_RUN",
            "google_business_profile": "NOT_RUN",
            "public_reviews": "NOT_RUN",
            "ahrefs_paid_api_units": 0,
            "sales_opportunity": "NIET_BEWEZEN",
        }
    except Exception:
        # Never log customer URL, site HTML, DNS or credential exception text.
        return "NIET_VERIFIEERBAAR", {"reason": "public_probe_failed"}


def _get(conn, base, name):
    response = conn.get(base + "/values/" + quote(name, safe=""), timeout=35)
    if response.status_code != 200:
        raise RuntimeError("private_read_failed")
    return response.json().get("values") or []


def _tab_id(conn, base):
    response = conn.get(base + "?fields=sheets(properties(sheetId,title))", timeout=20)
    if response.status_code != 200:
        raise RuntimeError("private_tab_metadata_failed")
    tabs = [t["properties"] for t in response.json().get("sheets", [])]
    found = [t["sheetId"] for t in tabs if t["title"] == TAB]
    if len(found) > 1:
        raise RuntimeError("private_duplicate_tab")
    if found:
        return found[0]
    created = conn.post(base + ":batchUpdate", json={"requests": [{"addSheet": {
        "properties": {"title": TAB, "gridProperties": {"rowCount": 10000,
                                               "columnCount": len(HEADERS), "frozenRowCount": 1}}
    }}]}, timeout=30)
    if created.status_code != 200:
        raise RuntimeError("private_add_tab_failed")
    sheets = created.json().get("replies") or []
    if len(sheets) != 1:
        raise RuntimeError("private_add_tab_readback_invalid")
    sid = sheets[0].get("addSheet", {}).get("properties", {}).get("sheetId")
    if not isinstance(sid, int):
        raise RuntimeError("private_add_tab_readback_invalid")
    return sid


def _cells(rows):
    return [{"values": [{"userEnteredValue": {"stringValue": str(x)}}
                        for x in row]} for row in rows]


def store_private_evidence(conn, base, proposed):
    """Append-only private readback: never erase an existing audit or lead."""
    if not proposed or len(proposed) > MAX_GOAL or any(len(r) != len(HEADERS) for r in proposed):
        raise ValueError("private_audit_rows_invalid")
    sid = _tab_id(conn, base)
    current = _get(conn, base, TAB + "!A1:G10000")
    if current and current[0] != list(HEADERS):
        raise RuntimeError("private_audit_headers_invalid")
    existing = {}
    for row in current[1:]:
        if len(row) != len(HEADERS):
            raise RuntimeError("private_audit_row_invalid")
        k = (row[0], row[1], row[3])
        if k in existing:
            raise RuntimeError("private_audit_duplicate")
        existing[k] = row
    to_append = []
    for row in proposed:
        k = (row[0], row[1], row[3])
        if k in existing:
            if existing[k] != row:
                # Existing historical audit must never be silently overwritten.
                # A rerun with new checked_at is not an idempotent replay.
                continue
        else:
            to_append.append(row)
    requests = []
    if not current:
        requests.append({"updateCells": {"range": {"sheetId": sid,
            "startRowIndex": 0, "endRowIndex": 1, "startColumnIndex": 0,
            "endColumnIndex": len(HEADERS)}, "rows": _cells([HEADERS]),
            "fields": "userEnteredValue"}})
    if to_append:
        requests.append({"appendCells": {"sheetId": sid, "rows": _cells(to_append),
                                           "fields": "userEnteredValue"}})
    if requests:
        response = conn.post(base + ":batchUpdate", json={"requests": requests}, timeout=45)
        if response.status_code != 200:
            raise RuntimeError("private_audit_write_failed")
    got = _get(conn, base, TAB + "!A1:G10000")
    if not got or got[0] != list(HEADERS):
        raise RuntimeError("private_audit_readback_headers_invalid")
    keys = {(r[0], r[1], r[3]): r for r in got[1:] if len(r) == len(HEADERS)}
    if not all((r[0], r[1], r[3]) in keys and
               keys[(r[0], r[1], r[3])][2] == r[2]
               for r in proposed):
        raise RuntimeError("private_audit_readback_failed")
    return len(to_append)


def run(*, session=None, fetch=None, analyze=None):
    """Complete source gate; scan public sites; private-only result commit."""
    from approved_handoff import _read_history
    from fast_website_evidence import _read
    from leads_chat_command import requested_goal, validate
    from private_candidate_handoff import SHEET_ID, authorized_writer
    from pathlib import Path

    event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text("utf-8"))
    goal = requested_goal(validate(event, event_name=os.environ.get("GITHUB_EVENT_NAME")))
    run_id = os.environ.get("GITHUB_RUN_ID", "")
    if (goal is None or str(goal) != os.environ.get("EXPECTED_LEAD_GOAL") or
            not re.fullmatch(r"[0-9]{1,20}", run_id) or
            os.environ.get("GITHUB_RUN_ATTEMPT") != "1"):
        raise RuntimeError("private_owner_gate_invalid")
    conn = session or authorized_writer()
    base = "https://sheets.googleapis.com/v4/spreadsheets/" + SHEET_ID
    history = _read_history(conn, base)
    evidence = _read(conn, "WebsiteEvidence!A1:N2200")
    records = select_verified(history, evidence, run_id, goal)
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        results = list(pool.map(lambda item: inspect_site(item["url"], fetch=fetch, analyze=analyze), records))
    again = select_verified(_read_history(conn, base),
                            _read(conn, "WebsiteEvidence!A1:N2200"), run_id, goal)
    if records != again:
        raise RuntimeError("private_source_changed_during_probe")
    stamp = datetime.now(timezone.utc).isoformat()
    proposals = []
    for item, (status, details) in zip(records, results):
        if status not in ALLOWED_STATUS:
            raise RuntimeError("invalid_probe_status")
        proposals.append([run_id, item["record_key"], item["source_sha256"],
                          CHECKER, stamp, status,
                          json.dumps(details, ensure_ascii=True, sort_keys=True, separators=(",", ":"))])
    written = store_private_evidence(conn, base, proposals)
    return {"verified":len(records), "audited":len(proposals), "added":written,
            "unverified":sum(status!="BEVESTIGD" for status,_ in results),
            "ahrefs_units":0, "mail_writes":0}


def main():
    try:
        summary = run()
        # Never emit public names, domain lists or raw site error messages.
        print("PRIVATE_TECH_AUDIT=complete verified=" + str(summary["verified"]) +
              " inspected=" + str(summary["audited"]) +
              " added=" + str(summary["added"]) +
              " uncertain=" + str(summary["unverified"]) +
              " ahrefs_units=0")
        return 0
    except Exception:
        print("PRIVATE_TECH_AUDIT=blocked")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
