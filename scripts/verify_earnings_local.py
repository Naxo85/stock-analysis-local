"""Read published examples and exercise display only; never modifies reports."""
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'gcp_services/stock_controller/src'))
from stock_analysis.earnings_calendar import calendar_from_reports, earnings_alert

payloads = {}
for symbol in ('SPCX', 'LRCX'):
    with urlopen('https://reports-714254943648.europe-southwest1.run.app?symbol=' + symbol, timeout=40) as response:
        payloads[symbol] = json.load(response)
calendar = calendar_from_reports(payloads)
result = {'read_at': datetime.now(timezone.utc).isoformat(), 'read_only': True, 'examples': {}}
for symbol in payloads:
    result['examples'][symbol] = {'report_at': payloads[symbol].get('generated_at'), 'calendar': calendar.get(symbol),
        'on_oct20': earnings_alert(calendar.get(symbol), now=datetime(2026, 10, 20, 12, tzinfo=timezone.utc)),
        'on_oct21': earnings_alert(calendar.get(symbol), now=datetime(2026, 10, 21, 12, tzinfo=timezone.utc))}
out = ROOT / 'docs/audit_earnings_20261021'
out.mkdir(parents=True, exist_ok=True)
(out / 'published_examples.json').write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding='utf-8')
print(json.dumps(result, ensure_ascii=True))
