#!/usr/bin/env python3
import argparse
import json
import statistics
from pathlib import Path

METRIC_AUDITS = {
    "first_contentful_paint": "first-contentful-paint",
    "largest_contentful_paint": "largest-contentful-paint",
    "total_blocking_time": "total-blocking-time",
    "cumulative_layout_shift": "cumulative-layout-shift",
    "speed_index": "speed-index",
    "interactive": "interactive",
    "server_response_time": "server-response-time",
}


def _number(value):
    return float(value) if isinstance(value, (int, float)) else None


def _median(values):
    clean = [_number(v) for v in values]
    clean = [v for v in clean if v is not None]
    return round(statistics.median(clean), 4) if clean else None


def load_lhr(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("categories"), dict) or not isinstance(data.get("audits"), dict):
        raise ValueError(f"{path} is geen Lighthouse LHR JSON")
    return data


def summarize_run(data, source_path=None):
    categories = {}
    for key, value in (data.get("categories") or {}).items():
        if not isinstance(value, dict):
            continue
        score = _number(value.get("score"))
        categories[key] = round(score, 4) if score is not None else None

    audits = data.get("audits") or {}
    metrics = {}
    for output_key, audit_id in METRIC_AUDITS.items():
        audit = audits.get(audit_id) or {}
        if not isinstance(audit, dict):
            continue
        numeric = _number(audit.get("numericValue"))
        metrics[output_key] = {
            "numeric_value": round(numeric, 3) if numeric is not None else None,
            "numeric_unit": audit.get("numericUnit"),
            "display_value": audit.get("displayValue"),
            "score": audit.get("score"),
        }

    seo_failures = []
    seo = (data.get("categories") or {}).get("seo") or {}
    for ref in seo.get("auditRefs") or []:
        if not isinstance(ref, dict) or not ref.get("id"):
            continue
        audit = audits.get(ref["id"]) or {}
        score = _number(audit.get("score"))
        mode = audit.get("scoreDisplayMode")
        if score is not None and score < 1 and mode not in {"notApplicable", "manual"}:
            seo_failures.append({
                "id": ref["id"],
                "title": audit.get("title"),
                "score": score,
                "display_value": audit.get("displayValue"),
            })

    return {
        "source_path": str(source_path) if source_path else None,
        "requested_url": data.get("requestedUrl"),
        "final_url": data.get("finalUrl"),
        "fetch_time": data.get("fetchTime"),
        "lighthouse_version": data.get("lighthouseVersion"),
        "categories": categories,
        "metrics": metrics,
        "seo_failures": seo_failures,
    }


def discover_lhrs(input_dir):
    root = Path(input_dir)
    valid = []
    for path in sorted(root.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(data, dict) and isinstance(data.get("categories"), dict) and isinstance(data.get("audits"), dict):
            valid.append(path)
    return valid


def build_summary(paths):
    runs = [summarize_run(load_lhr(path), path) for path in paths]
    if not runs:
        raise ValueError("geen Lighthouse LHR JSON-bestanden gevonden")

    category_keys = sorted({key for run in runs for key in run["categories"]})
    metric_keys = sorted({key for run in runs for key in run["metrics"]})
    median_categories = {key: _median([run["categories"].get(key) for run in runs]) for key in category_keys}
    median_metrics = {}
    for key in metric_keys:
        samples = [run["metrics"].get(key, {}).get("numeric_value") for run in runs]
        exemplar = next((run["metrics"].get(key) for run in runs if run["metrics"].get(key)), {})
        median_metrics[key] = {
            "numeric_value": _median(samples),
            "numeric_unit": exemplar.get("numeric_unit"),
        }

    return {
        "schema_version": "1.0",
        "run_count": len(runs),
        "median": {"categories": median_categories, "metrics": median_metrics},
        "runs": runs,
        "limitations": [
            "Lighthouse is labdata; gebruik CrUX/fielddata voor Core Web Vitals in het veld.",
            "SEO-categoriescores zijn diagnostische samenvattingen en geen rankingfactor of rankingvoorspelling.",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description="Normalize one or more Lighthouse CI LHR files")
    parser.add_argument("--input-dir", default=".lighthouseci")
    parser.add_argument("--output", default="reports/lighthouse-summary.json")
    args = parser.parse_args()
    summary = build_summary(discover_lhrs(args.input_dir))
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
