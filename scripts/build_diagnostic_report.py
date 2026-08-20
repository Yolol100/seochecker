#!/usr/bin/env python3
import argparse
import json
from pathlib import Path


def load_json(path):
    p = Path(path)
    if not p.exists():
        return {"status": "missing", "path": str(p)}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"status": "error", "error": f"kan {p} niet lezen: {exc}"}


def gsc_index_status(gsc):
    try:
        result = gsc.get("url_inspection", {}).get("inspectionResult", {}).get("indexStatusResult", {})
        return {
            "verdict": result.get("verdict"),
            "coverage_state": result.get("coverageState"),
            "robots_txt_state": result.get("robotsTxtState"),
            "indexing_state": result.get("indexingState"),
            "page_fetch_state": result.get("pageFetchState"),
            "google_canonical": result.get("googleCanonical"),
            "user_canonical": result.get("userCanonical"),
            "last_crawl_time": result.get("lastCrawlTime"),
        }
    except AttributeError:
        return {}


def build_signals(basic, language, gsc, ahrefs):
    signals = []
    blockers = basic.get("indexability_blockers") or []
    if blockers:
        signals.append({"severity": "high", "type": "technical_indexability", "evidence": blockers, "score": 5})

    if language.get("status") == "ok" and language.get("language_matches_expected") is False:
        signals.append({
            "severity": "high",
            "type": "language_mismatch",
            "evidence": {"expected": language.get("expected_lang"), "html_lang": language.get("html_lang")},
            "score": 4,
        })

    if gsc.get("status") == "ok":
        idx = gsc_index_status(gsc)
        if idx.get("verdict") and idx.get("verdict") != "PASS":
            signals.append({"severity": "high", "type": "google_index_status", "evidence": idx, "score": 6})
        comp = gsc.get("target_country", {}).get("period_comparison", {})
        change = comp.get("impressions_change_pct")
        if isinstance(change, (int, float)) and change <= -80:
            signals.append({"severity": "high", "type": "gsc_visibility_drop", "evidence": comp, "score": 5})
        elif isinstance(change, (int, float)) and change <= -40:
            signals.append({"severity": "medium", "type": "gsc_visibility_drop", "evidence": comp, "score": 3})
        sitemap_summary = gsc.get("submitted_sitemaps", {})
        sitemap_issues = sitemap_summary.get("with_errors_or_warnings_count")
        if isinstance(sitemap_issues, int) and sitemap_issues > 0:
            signals.append({
                "severity": "medium",
                "type": "gsc_sitemap_issues",
                "evidence": sitemap_summary,
                "score": 2,
            })

    if ahrefs.get("status") == "ok":
        anchor = ahrefs.get("anchor_summary", {})
        spam = ahrefs.get("refdomains_sample_summary", {})
        suspicious_refdomains = int(anchor.get("suspicious_refdomains_sum", 0) or 0)
        spam_pct = spam.get("ahrefs_spam_sample_pct")
        if suspicious_refdomains >= 25 or (isinstance(spam_pct, (int, float)) and spam_pct >= 50):
            signals.append({
                "severity": "high",
                "type": "automated_backlink_spam",
                "evidence": {"anchor_summary": anchor, "refdomain_sample_summary": spam},
                "score": 4,
            })
        elif suspicious_refdomains >= 5:
            signals.append({
                "severity": "medium",
                "type": "suspicious_backlinks",
                "evidence": {"anchor_summary": anchor, "refdomain_sample_summary": spam},
                "score": 2,
            })
    return sorted(signals, key=lambda s: s.get("score", 0), reverse=True)


def open_evidence(gsc, ahrefs):
    items = []
    if gsc.get("status") != "ok":
        items.append("Google Search Console API-data ontbreekt of kon niet worden opgehaald.")
    else:
        items.append("Controleer in Search Console handmatig: Handmatige acties en Beveiligingsproblemen.")
    if ahrefs.get("status") != "ok":
        items.append("Ahrefs API-data ontbreekt of kon niet worden opgehaald.")
    return items


def build_markdown(target_url, signals, basic, language, gsc, ahrefs, open_items):
    lines = [
        "# SEO Diagnostic Report",
        "",
        f"Target: `{target_url}`",
        "",
        "## Belangrijkste signalen",
        "",
    ]
    if not signals:
        lines.append("Geen dominante oorzaak bewezen met de beschikbare evidence.")
    else:
        labels = {
            "technical_indexability": "Technische indexeerbaarheidsblokkade",
            "language_mismatch": "Taalinstelling wijkt af",
            "google_index_status": "Google URL Inspection geeft geen PASS",
            "gsc_visibility_drop": "Sterke daling in GSC-vertoningen",
            "gsc_sitemap_issues": "Search Console meldt sitemap-waarschuwingen of -fouten",
            "automated_backlink_spam": "Sterk signaal van geautomatiseerde backlinkspam",
            "suspicious_backlinks": "Verdachte backlinkpatronen",
        }
        for signal in signals:
            lines.append(f"- **{signal['severity'].upper()}** — {labels.get(signal['type'], signal['type'])}")
    lines.extend(["", "## Evidence-overzicht", ""])
    lines.append(f"- Technische blockers: {len(basic.get('indexability_blockers') or [])}")
    if language.get("status") == "ok":
        lines.append(f"- HTML-taal: `{language.get('html_lang')}`; verwacht: `{language.get('expected_lang')}`; match: `{language.get('language_matches_expected')}`")
    else:
        lines.append(f"- Taalprobe: `{language.get('status')}`")
    if gsc.get("status") == "ok":
        idx = gsc_index_status(gsc)
        comp = gsc.get("target_country", {}).get("period_comparison", {})
        sitemaps = gsc.get("submitted_sitemaps", {})
        lines.append(f"- GSC URL Inspection verdict: `{idx.get('verdict')}`; coverage: `{idx.get('coverage_state')}`")
        lines.append(f"- GSC target-country impressions change (laatste 28d vs vorige 28d): `{comp.get('impressions_change_pct')}`%")
        lines.append(f"- GSC ingediende/bekende sitemaps: `{sitemaps.get('submitted_count')}`; met fouten/waarschuwingen: `{sitemaps.get('with_errors_or_warnings_count')}`; pending: `{sitemaps.get('pending_count')}`")
    else:
        lines.append(f"- GSC: `{gsc.get('status')}` — {gsc.get('reason') or gsc.get('error') or 'geen data'}")
    if ahrefs.get("status") == "ok":
        history = ahrefs.get("refdomains_history_summary", {})
        anchor = ahrefs.get("anchor_summary", {})
        spam = ahrefs.get("refdomains_sample_summary", {})
        lines.append(f"- Ahrefs referring-domain groei in meetvenster: `{history.get('growth')}`")
        lines.append(f"- Verdachte anchor-refdomains (som binnen anchor-sample): `{anchor.get('suspicious_refdomains_sum')}`")
        lines.append(f"- Ahrefs-spam in nieuwste referring-domain-sample: `{spam.get('ahrefs_spam_sample_pct')}`%")
    else:
        lines.append(f"- Ahrefs: `{ahrefs.get('status')}` — {ahrefs.get('reason') or ahrefs.get('error') or 'geen data'}")

    lines.extend(["", "## Bewijsgrens", ""])
    lines.append("Dit rapport bewijst geen algoritmische of handmatige Google-penalty. Het combineert technische live-data, GSC first-party data en Ahrefs third-party backlinkdata en houdt die bronnen gescheiden.")
    if open_items:
        lines.extend(["", "## Nog handmatig/open", ""])
        for item in open_items:
            lines.append(f"- {item}")
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description="Combine technical, GSC and Ahrefs evidence")
    parser.add_argument("--target-url", required=True)
    parser.add_argument("--basic", default="reports/basic-seo.json")
    parser.add_argument("--language", default="reports/language-report.json")
    parser.add_argument("--gsc", default="reports/gsc-report.json")
    parser.add_argument("--ahrefs", default="reports/ahrefs-report.json")
    parser.add_argument("--output-json", default="reports/diagnostic-summary.json")
    parser.add_argument("--output-md", default="reports/diagnostic-summary.md")
    args = parser.parse_args()

    basic = load_json(args.basic)
    language = load_json(args.language)
    gsc = load_json(args.gsc)
    ahrefs = load_json(args.ahrefs)
    signals = build_signals(basic, language, gsc, ahrefs)
    open_items = open_evidence(gsc, ahrefs)
    payload = {
        "target_url": args.target_url,
        "signals": signals,
        "technical": basic,
        "language": language,
        "gsc": gsc,
        "ahrefs": ahrefs,
        "open_evidence": open_items,
        "decision_rule": "Prioriteer bewezen technische/indexatieblokkades boven ranking/backlinkhypotheses; gebruik GSC als hoogste bewijslaag voor eigen Google-zichtbaarheid.",
    }
    out_json = Path(args.output_json)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    out_md = Path(args.output_md)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(build_markdown(args.target_url, signals, basic, language, gsc, ahrefs, open_items), encoding="utf-8")
    print(out_json)
    print(out_md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
