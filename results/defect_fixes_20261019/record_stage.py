"""Save reviewable per-task diffs and test evidence; Python stdlib only."""
from pathlib import Path
import difflib
import json
import shutil
import sys
import xml.etree.ElementTree as ET

folder = Path(__file__).resolve().parent
root = Path(sys.argv[3]) if len(sys.argv) > 3 else folder.parent.parent / 'mobile' / 'android'
stage, previous = sys.argv[1:3]
snapshot = folder / stage
for rel in ('app/src', 'app/build.gradle.kts', 'DEVICE_TEST_REPORT.md', 'GLOSSARY_ALTERNATIVES_REVIEW.md'):
    src, dst = root / rel, snapshot / rel
    if not src.exists():
        continue
    if src.is_dir():
        shutil.copytree(src, dst, dirs_exist_ok=True)
    else:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
before = folder / previous
paths = sorted({p.relative_to(before) for p in before.rglob('*') if p.is_file()} |
               {p.relative_to(snapshot) for p in snapshot.rglob('*') if p.is_file()})
diff = []
summary = []
for rel in paths:
    old = (before / rel).read_text(encoding='utf-8').splitlines(keepends=True) if (before / rel).exists() else []
    new = (snapshot / rel).read_text(encoding='utf-8').splitlines(keepends=True) if (snapshot / rel).exists() else []
    changes = list(difflib.unified_diff(old, new, fromfile='a/' + rel.as_posix(), tofile='b/' + rel.as_posix()))
    if changes:
        diff.extend(changes)
        summary.append({'file': rel.as_posix(),
                        'added': sum(l.startswith('+') and not l.startswith('+++') for l in changes),
                        'removed': sum(l.startswith('-') and not l.startswith('---') for l in changes)})
(folder / (stage + '.diff')).write_text(''.join(diff), encoding='utf-8')
totals = dict(tests=0, failures=0, errors=0, skipped=0)
test_dir = folder / (stage + '_tests')
test_dir.mkdir(exist_ok=True)
for report in (root / 'app/build/test-results/testDebugUnitTest').glob('TEST-*.xml'):
    suite = ET.parse(report).getroot()
    for key in totals:
        totals[key] += int(suite.get(key, '0'))
    shutil.copy2(report, test_dir / report.name)
record = {'stage': stage, 'diff': summary, 'unit_tests': totals}
(folder / (stage + '_summary.json')).write_text(json.dumps(record, indent=2), encoding='utf-8')
print(json.dumps(record, indent=2))
