"""Verify the deployed calendar/API without model calls or report writes."""
from datetime import datetime, timezone
import json
from pathlib import Path
from urllib.request import Request, urlopen
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'gcp_services/stock_controller/src'))
from stock_analysis.earnings_calendar import earnings_alert

personal = ROOT / '.local/mobile'
url = json.loads((personal / 'deployment.json').read_text())['url']
code = (personal / 'access-code.txt').read_text().strip()
with urlopen(Request(url + '/v1/dashboard', headers={'Authorization': 'Bearer ' + code}), timeout=120) as response:
    assert response.status == 200
    payload = json.load(response)
assert not payload['stale'] and not payload['warnings'], payload.get('warnings')
now = datetime.now(timezone.utc)
stocks = {stock['symbol']: stock for stock in payload['stocks']}
assert len(stocks) >= 40
for symbol, stock in stocks.items():
    assert 'earnings' in stock and 'earnings_alert' in stock, 'old_mobile_revision:' + symbol
    assert stock['earnings_alert'] == earnings_alert(stock['earnings'], now=now), 'calendar_mismatch:' + symbol
assert stocks['LRCX']['earnings']['date'] == '2026-10-21'
assert stocks['LRCX']['earnings_alert']['severity'] == 'red'
assert stocks['SPCX']['earnings_alert'] is None
result = {'verified_at': now.isoformat(), 'snapshot_at': payload['generated_at'], 'stocks': len(stocks),
          'same_calendar_logic': True, 'warnings': payload['warnings'],
          'alerts': {s: v['earnings_alert'] for s, v in stocks.items() if v['earnings_alert']},
          'stock_authority': {s: {'shots': v['shots'], 'publication_version': v.get('publication_version'),
                                  'analysis_at': v['analysis_at']} for s, v in stocks.items()},
          'LRCX_report_at': stocks['LRCX']['analysis_at'], 'SPCX_report_at': stocks['SPCX']['analysis_at']}
(ROOT / 'docs/audit_earnings_20261021/mobile_parity.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(result, ensure_ascii=True))
