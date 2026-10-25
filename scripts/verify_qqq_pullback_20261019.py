"""Verify real mobile/Sheets parity without exposing authentication material."""
from datetime import datetime, timezone
import json
import sys
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs/audit_qqq_pullback_20261019'
if '--compact' in sys.argv:
    OUT = OUT / 'compact'
personal = ROOT / '.local/mobile'
url = json.loads((personal / 'deployment.json').read_text())['url']
token = (personal / 'access-code.txt').read_text().strip()
with urlopen(Request(url + '/v1/dashboard', headers={'Authorization': 'Bearer ' + token}), timeout=120) as response:
    assert response.status == 200
    payload = json.load(response)
assert not payload['stale'] and not payload['warnings']
actual = payload['market']['qqq_pullback']
expected = json.loads((OUT / 'sheet_expected.json').read_text(encoding='utf-8'))
assert actual is not None
for key, value in expected.items():
    assert actual[key] == value, 'sheet_mobile_mismatch:' + key
result = {'verified_at': datetime.now(timezone.utc).isoformat(),
          'snapshot_at': payload['generated_at'], 'same_sheet_values': True,
          'qqq_pullback': {key: actual[key] for key in expected}}
(OUT / 'mobile_parity.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(result, ensure_ascii=True))
