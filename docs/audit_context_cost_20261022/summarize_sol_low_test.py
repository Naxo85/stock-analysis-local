import json,sys
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
folder=Path(sys.argv[1])
rows=json.loads((folder/'results.json').read_text(encoding='utf-8')) if (folder/'results.json').exists() else []
usage=Counter();baseline=Counter();comparisons=[]
for row in rows:
    usage.update(row.get('usage',{}))
    source=ROOT/'logs/batch/2026-10-23/14-18-22/adaptive'/row['ticker']
    old=json.loads((source/'triage.json').read_text(encoding='utf-8'))
    old_receipt=json.loads((source/'triage.receipt.json').read_text(encoding='utf-8'))
    baseline.update(old_receipt.get('usage',{}))
    comparisons.append({'ticker':row['ticker'],'luna_initial':old['decision'],
        'sol_low':row.get('decision'),'validated':row['validated'], 'usage':row.get('usage'),
        'errors':row.get('errors'), 'reason':row.get('reason')})
quotas={}
for key in ('before','after'):
    file=folder/('quota_'+key+'.json')
    if file.exists():quotas[key]=json.loads(file.read_text(encoding='utf-8'))
output={'folder':str(folder),'cases':comparisons,'sol_low_usage':usage,'luna_initial_usage':baseline,'quotas':quotas}
(folder/'summary.json').write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(output,ensure_ascii=True,indent=2))
