"""Trace original visible14 ranges through stored decisions; no financial inference."""
import json
import sys
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8')
ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).parent
data=json.loads((OUT/'census.json').read_text(encoding='utf-8'))
removed=[z for z in data['same_range_14_to_18']['removed'] if z['total']>=65]
paths=[
    '2026-10-15/07-21-28','2026-10-15/12-01-08',
    '2026-10-16/15-58-24','2026-10-18/09-08-40',
]
def load(p):return json.loads(p.read_text(encoding='utf-8'))
def document(x):return x['semantic_report']['data']
def contains(doc,rg):return any((doc['plan'][k] or {}).get('range')==rg for k in ('entry','ambitious_entry'))
result=[]
for old in removed:
    row={'symbol':old['symbol'],'old_slot':old['slot'],'old_range':old['range'],'old_total':old['total'],'events':[]}
    for stamp in paths:
        base=ROOT/'logs/batch'/stamp/'adaptive'/old['symbol']
        if not (base/'publish/current_state.json').exists():continue
        before=document(load(base/'input.json')['reference']);after=document(load(base/'publish/current_state.json'))
        if contains(before,old['range']) and not contains(after,old['range']):
            t=load(base/'triage.json')
            row['events'].append({'batch':stamp,'decision':t['decision'],'reason':t.get('reason'),'after':{k:{'range':after['plan'][k].get('range'),'strength':after['plan'][k].get('strength'),'reason':after['plan'][k].get('reason'),'change_review':after['plan'][k].get('change_review')} for k in ('entry','ambitious_entry')}})
    result.append(row)
(OUT/'visible14_removed_trace.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps([{k:v for k,v in row.items() if k!='events'}|{'events':[{'batch':e['batch'],'reason':e['reason']} for e in row['events']]} for row in result],ensure_ascii=False,indent=2))
