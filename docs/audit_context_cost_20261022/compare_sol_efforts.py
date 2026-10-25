"""Summarize only completed low/medium calls; no models or publication."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
medium=Path(sys.argv[1]).resolve()
plan=json.loads((medium/'plan.json').read_text(encoding='utf-8'))
low=Path(plan['baseline'])
groups={};cases={}
for label,folder in [('low',low),('medium',medium)]:
    file=folder/'results.json'
    rows=json.loads(file.read_text(encoding='utf-8')) if file.exists() else []
    total=Counter()
    for row in rows:
        total.update(row.get('usage',{}))
        cases.setdefault(row['ticker'],{})[label]={key:row.get(key) for key in
            ('decision','validated','errors','risk','reason','usage','seconds','execution_error')}
    quotas={}
    for key in ('before','after'):
        file=folder/('quota_'+key+'.json')
        if file.exists():quotas[key]=json.loads(file.read_text(encoding='utf-8'))
    groups[label]={'completed_cases':len(rows),'usage':total,'quotas':quotas}
identical={}
for symbol in plan['tickers']:
    identical[symbol]={}
    for name in ('frozen_context.json','view.json','schema.json','expected.input.json'):
        first=(low/symbol/name).read_bytes();second=(medium/symbol/name).read_bytes()
        assert first==second
        identical[symbol][name]=hashlib.sha256(first).hexdigest()
output={'groups':groups,'cases':cases,'identical_fixtures':identical,
        'comparison_limit':'One response per case/effort; effort setting and matching footer label differ; temporal/cache order uncontrolled.'}
(medium/'comparison.json').write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'groups':groups,'cases':cases},ensure_ascii=True,indent=2))
