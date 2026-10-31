#!/usr/bin/env bash
set -euo pipefail
# Use the locked Lighthouse CLI directly; never invoke the vulnerable LHCI wrapper.
if [ "$#" -ne 2 ]; then echo 'Usage: run_lighthouse_three.sh <trusted-url> <empty-output-directory>' >&2; exit 2; fi
url="$1"
out="$2"
if [ -z "$url" ] || [ -z "$out" ]; then echo 'A trusted URL and output directory are required' >&2; exit 2; fi
if [ -d "$out" ] && find "$out" -maxdepth 1 -type f -name 'lhr-*.json' | grep -q .; then
  echo 'Existing Lighthouse evidence must not be overwritten or mixed with new runs' >&2
  exit 1
fi
mkdir -p "$out"
for index in 1 2 3; do
  ./node_modules/.bin/lighthouse "$url" --output=json --output-path="$out/lhr-$index.json" --chrome-flags='--headless --no-sandbox --disable-dev-shm-usage'
done
python3 - "$out" "$url" <<'PY'
import json, sys
from pathlib import Path
from urllib.parse import urlsplit
folder, target = Path(sys.argv[1]), urlsplit(sys.argv[2])
files = sorted(folder.glob('lhr-*.json'))
if len(files) != 3:
    raise SystemExit('Expected exactly three independent Lighthouse JSON reports')
versions = set()
for path in files:
    doc = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(doc.get('categories'), dict) or not isinstance(doc.get('audits'), dict):
        raise SystemExit(f'Malformed LHR: {path.name}')
    if urlsplit(doc.get('requestedUrl', '')).hostname != target.hostname:
        raise SystemExit(f'Lighthouse host mismatch: {path.name}')
    versions.add(doc.get('lighthouseVersion'))
if versions != {'13.4.1'}:
    raise SystemExit('Unexpected Lighthouse version across LHR reports')
print('Three real Lighthouse 13.4.1 reports verified')
PY
