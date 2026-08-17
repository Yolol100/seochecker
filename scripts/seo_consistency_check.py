#!/usr/bin/env python3
import argparse
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

try:
    from .seo_basic_check import _normalize_url, analyze_html, probe
except ImportError:
    from seo_basic_check import _normalize_url, analyze_html, probe

DEFAULT_MAX_HREFLANG = 20
DEFAULT_MAX_SITEMAPS = 5


def _unique_urls(values):
    seen = set()
    result = []
    for value in values:
        if not isinstance(value, str) or not value.strip():
            continue
        normalized = _normalize_url(value.strip())
        if normalized in seen:
            continue
        seen.add(normalized)
        result.append(value.strip())
    return result


def _local_name(tag):
    return str(tag).rsplit('}', 1)[-1].lower()


def _parse_sitemap(body):
    root = ET.fromstring(body)
    kind = _local_name(root.tag)
    locations = []
    for element in root.iter():
        if _local_name(element.tag) == 'loc' and element.text and element.text.strip():
            locations.append(element.text.strip())
    return kind, locations


def check_hreflang_reciprocity(final_url, hreflang, probe_fn=probe, max_urls=DEFAULT_MAX_HREFLANG):
    declared = _unique_urls([item.get('url', '') for item in hreflang if isinstance(item, dict)])
    if not declared:
        return {
            'applicable': False,
            'declared_urls': 0,
            'checked_urls': 0,
            'truncated': False,
            'reciprocal_ok': None,
            'missing_return_links': [],
            'unresolved': [],
        }

    current = _normalize_url(final_url)
    selected = declared[:max_urls]
    missing = []
    unresolved = []
    checked = 0

    for target in selected:
        target_normalized = _normalize_url(target)
        if target_normalized == current:
            checked += 1
            continue

        response = probe_fn(target, 12)
        status = response.get('status')
        body = response.get('body', '')
        resolved_url = response.get('final_url') or target
        if status is None or status >= 400 or not body:
            unresolved.append({
                'url': target,
                'status': status,
                'error': response.get('error'),
            })
            continue

        checked += 1
        analyzed = analyze_html(body, resolved_url)
        return_urls = {
            _normalize_url(item.get('url', ''))
            for item in analyzed.get('hreflang', [])
            if isinstance(item, dict) and item.get('url')
        }
        if current not in return_urls:
            missing.append(target)

    truncated = len(declared) > len(selected)
    reciprocal_ok = not missing and not unresolved and not truncated
    return {
        'applicable': True,
        'declared_urls': len(declared),
        'checked_urls': checked,
        'truncated': truncated,
        'reciprocal_ok': reciprocal_ok,
        'missing_return_links': missing,
        'unresolved': unresolved,
    }


def inspect_sitemaps(final_url, sitemap_urls, probe_fn=probe, max_sitemaps=DEFAULT_MAX_SITEMAPS):
    queue = _unique_urls(sitemap_urls)
    if not queue:
        return {
            'checked_sitemaps': [],
            'contains_final_url': None,
            'truncated': False,
            'errors': [],
        }

    target = _normalize_url(final_url)
    checked = []
    errors = []
    seen = set()

    while queue and len(checked) < max_sitemaps:
        sitemap_url = queue.pop(0)
        normalized_sitemap = _normalize_url(sitemap_url)
        if normalized_sitemap in seen:
            continue
        seen.add(normalized_sitemap)

        response = probe_fn(sitemap_url, 12)
        status = response.get('status')
        body = response.get('body', '')
        checked.append(sitemap_url)
        if status is None or status >= 400 or not body:
            errors.append({
                'url': sitemap_url,
                'status': status,
                'error': response.get('error'),
            })
            continue

        try:
            kind, locations = _parse_sitemap(body)
        except ET.ParseError as exc:
            errors.append({'url': sitemap_url, 'error': f'invalid XML: {exc}'})
            continue

        if kind == 'urlset':
            if target in {_normalize_url(url) for url in locations}:
                return {
                    'checked_sitemaps': checked,
                    'contains_final_url': True,
                    'truncated': False,
                    'errors': errors,
                }
        elif kind == 'sitemapindex':
            for child in _unique_urls(locations):
                if _normalize_url(child) not in seen:
                    queue.append(child)
        else:
            errors.append({'url': sitemap_url, 'error': f'unsupported sitemap root: {kind}'})

    truncated = bool(queue)
    if truncated or errors:
        contains = None
    else:
        contains = False
    return {
        'checked_sitemaps': checked,
        'contains_final_url': contains,
        'truncated': truncated,
        'errors': errors,
    }


def build_consistency_report(basic, probe_fn=probe, max_hreflang=DEFAULT_MAX_HREFLANG, max_sitemaps=DEFAULT_MAX_SITEMAPS):
    final_url = basic.get('http', {}).get('final_url') or basic.get('requested_url')
    if not final_url:
        raise ValueError('basic SEO report has no final URL')

    hreflang = check_hreflang_reciprocity(
        final_url,
        basic.get('hreflang', []),
        probe_fn=probe_fn,
        max_urls=max_hreflang,
    )
    sitemap = inspect_sitemaps(
        final_url,
        basic.get('sitemap_candidates', []),
        probe_fn=probe_fn,
        max_sitemaps=max_sitemaps,
    )

    conflicts = []
    blockers = basic.get('indexability_blockers', [])
    noindex = any('noindex' in str(item).lower() for item in blockers)
    canonical = basic.get('canonical', [])
    canonical_elsewhere = (
        len(canonical) == 1
        and _normalize_url(canonical[0]) != _normalize_url(final_url)
    )

    if sitemap.get('contains_final_url') is True and noindex:
        conflicts.append({
            'code': 'sitemap_noindex_conflict',
            'message': 'De uiteindelijke URL staat in een sitemap maar bevat een noindex-signaal.',
        })
    if sitemap.get('contains_final_url') is True and canonical_elsewhere:
        conflicts.append({
            'code': 'sitemap_canonical_conflict',
            'message': 'De uiteindelijke URL staat in een sitemap maar canonicaliseert naar een andere URL.',
        })
    if hreflang.get('applicable') and hreflang.get('missing_return_links'):
        conflicts.append({
            'code': 'hreflang_missing_return_links',
            'message': 'Een of meer hreflang-alternatieven linken niet terug naar de uiteindelijke URL.',
        })

    return {
        'schema_version': '1.0',
        'final_url': final_url,
        'canonical_self_referencing': basic.get('canonical_self_referencing'),
        'hreflang_reciprocity': hreflang,
        'sitemap_membership': sitemap,
        'signal_conflicts': conflicts,
        'limitations': [
            f'hreflang-controle is begrensd tot maximaal {max_hreflang} unieke gedeclareerde alternatieven',
            f'sitemapcontrole is begrensd tot maximaal {max_sitemaps} sitemapbestanden',
            'onopgeloste of afgekapt gecontroleerde bronnen worden als onbekend gerapporteerd en niet als afwezig',
        ],
    }


def main():
    parser = argparse.ArgumentParser(description='Bounded canonical, hreflang and sitemap consistency check')
    parser.add_argument('--input', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--max-hreflang', type=int, default=DEFAULT_MAX_HREFLANG)
    parser.add_argument('--max-sitemaps', type=int, default=DEFAULT_MAX_SITEMAPS)
    args = parser.parse_args()

    try:
        basic = json.loads(Path(args.input).read_text(encoding='utf-8'))
        report = build_consistency_report(
            basic,
            max_hreflang=max(1, args.max_hreflang),
            max_sitemaps=max(1, args.max_sitemaps),
        )
    except Exception as exc:
        report = {'schema_version': '1.0', 'fatal_error': str(exc)}
        code = 2
    else:
        code = 0

    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(path)
    return code


if __name__ == '__main__':
    sys.exit(main())
