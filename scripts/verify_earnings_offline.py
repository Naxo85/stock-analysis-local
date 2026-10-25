"""Record the bounded offline regressions and final Android build evidence."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs/audit_earnings_20261021'
OUT.mkdir(parents=True, exist_ok=True)
modules = ['test_earnings', 'test_support_validity', 'test_analysis_reports', 'test_analysis_sheet',
           'test_analysis_score_persistence', 'test_analysis_sync_version', 'test_report_link_persistence',
           'test_normalized_report_link_sort', 'test_global_sheet_sort', 'test_ticker_link_repair', 'test_qqq_pullback']
env = dict(os.environ, PYTHONPATH=os.pathsep.join(str(ROOT / p) for p in
    ['gcp_services/stock_controller/src', 'gcp_services/stock_controller/tests']))
results = {}
for name, args, context in [
    ('controller', ['-m', 'unittest', *modules, '-v'], env),
    ('mobile', ['-m', 'unittest', 'discover', '-s', 'gcp_services/mobile_api/tests', '-v'], os.environ),
]:
    run = subprocess.run([sys.executable, *args], cwd=ROOT, env=context, capture_output=True, text=True, encoding='utf-8')
    log = run.stdout + run.stderr
    (OUT / (name + '_tests.log')).write_text(log, encoding='utf-8')
    assert run.returncode == 0, log
    results[name] = {'tests': int(re.search(r'Ran (\d+) tests', log)[1]), 'passed': True}
android = []
for path in (ROOT / 'android/app/build/test-results/testDebugUnitTest').glob('TEST-*.xml'):
    suite = ET.parse(path).getroot()
    android.append({key: suite.attrib[key] for key in ('name', 'tests', 'failures', 'errors')})
assert android and all(r['failures'] == r['errors'] == '0' for r in android)
apk = ROOT / 'releases/android/Growth-0.1.0.apk'
result = {'verified_at': datetime.now(timezone.utc).isoformat(), 'offline_regressions': results,
          'android_unit_tests': android, 'android_release_unit_lint_build': 'passed',
          'apk_sha256': hashlib.sha256(apk.read_bytes()).hexdigest(),
          'instrumented_ui': 'not run: private emulator requires an unavailable Android hypervisor driver',
          'production_deployment': 'pending explicit authorization after automatic review rejection',
          'no_financial_reports_or_sheet_modified': True}
(OUT / 'verification.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
print(json.dumps(result))
