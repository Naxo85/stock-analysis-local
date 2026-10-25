import json
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).resolve().parents[2]
out = {}
for day, hour in [('2026-10-21', '06-52-46'), ('2026-10-22', '12-32-48'), ('2026-10-23', '14-18-22')]:
    folder = ROOT / 'logs/batch' / day / hour
    budget = json.loads((folder / 'codex_budget.json').read_text(encoding='utf-8'))
    groups = {}
    calls = list(budget['calls'].values())
    for call in calls:
        key = call['kind'] + ':' + str(call.get('model'))
        group = groups.setdefault(key, {'calls': 0, 'statuses': Counter(), 'usage': Counter(), 'tickers': []})
        group['calls'] += 1
        group['statuses'][call['status']] += 1
        group['usage'].update(call.get('usage') or {})
        if call['kind'] == 'report':
            group['tickers'].append({'ticker': call['ticker'], 'itv': call.get('itv')})
    decisions = Counter()
    full_reasons = {}
    research = Counter()
    repaired_escalations = {}
    routing = {}
    for ticker in (folder / 'adaptive').iterdir():
        if not ticker.is_dir():
            continue
        review_path = ticker / 'review.json'
        if review_path.exists():
            review = json.loads(review_path.read_text(encoding='utf-8'))
            if any(r.get('model') == 'gpt-6.1-sol' for r in review.get('receipts', [])):
                routing[ticker.name] = {k: review.get(k) for k in ('maintenance_escalation', 'luna_repair', 'guards', 'status', 'review_flags')}
        for p in ticker.glob('*.receipt.json'):
            receipt = json.loads(p.read_text(encoding='utf-8'))
            research[p.name.split('.')[0]] += receipt.get('web_search_count', 0)
        p = ticker / 'triage.json'
        if p.exists():
            obj = json.loads(p.read_text(encoding='utf-8'))
            decisions[str(obj.get('decision'))] += 1
            if obj.get('decision') == 'escalate':
                full_reasons[ticker.name] = {k: v for k, v in obj.items() if k in ('decision', 'reason', 'rationale', 'risk_flags', 'escalation_reason')}
        p = ticker / 'triage_repair.json'
        if p.exists():
            obj = json.loads(p.read_text(encoding='utf-8'))
            if obj.get('decision') == 'escalate':
                repaired_escalations[ticker.name] = {k: v for k, v in obj.items() if k in ('decision', 'reason', 'risk_flags')}
    summary = json.loads((folder / 'summary.json').read_text(encoding='utf-8'))
    out[day] = {'groups': groups, 'decisions': decisions, 'full_reasons': full_reasons, 'repaired_escalations': repaired_escalations, 'routing': routing, 'web_searches': research, 'summary_scalars': {k:v for k,v in summary.items() if not isinstance(v,(dict,list))}}
target = Path(__file__).with_name('latest_batch_usage.json')
target.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
latest = out['2026-10-23']
extra = Counter()
for symbol in ('AMD', 'AMAT', 'SNDK', 'ASTS'):
    receipt = json.loads((ROOT/'logs/batch/2026-10-23/14-18-22/adaptive'/symbol/'report.receipt.json').read_text(encoding='utf-8'))
    extra.update(receipt.get('usage') or {})
latest['four_automatic_full_usage'] = extra
target.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'groups': latest['groups'], 'four_automatic_full_usage': extra}, ensure_ascii=True, indent=2))
