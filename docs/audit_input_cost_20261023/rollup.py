"""Recorded usage and byte/character provenance; no inference of weekly billing."""
from collections import Counter,defaultdict
from pathlib import Path
from statistics import median
import json,sys,hashlib
ROOT=Path(__file__).resolve().parents[2]
BATCH=ROOT/'logs/batch/2026-10-23/14-18-22'
inventory=json.loads(Path(__file__).with_name('inventory.json').read_text(encoding='utf-8'))
variants=json.loads(Path(__file__).with_name('variants.json').read_text(encoding='utf-8'))
budget=json.loads((BATCH/'codex_budget.json').read_text(encoding='utf-8'))
rates={'gpt-6-luna':(2.5,.25,12.5),'gpt-6.1-sol':(50,2.5,250)}
groups=defaultdict(lambda:{'calls':0,'with_usage':0,'usage':Counter(),'credit_proxy':0})
extra=Counter();rows=[]
for call in budget['calls'].values():
    group=groups[call['kind']];group['calls']+=1
    usage=call.get('usage')
    if not usage:continue
    group['with_usage']+=1;group['usage'].update(usage)
    rate=rates[call['model']]
    credit=(usage['uncached_input_tokens']*rate[0]+usage['cached_input_tokens']*rate[1]+usage['output_tokens']*rate[2])/1e6
    group['credit_proxy']+=credit
    if call['kind']=='report' and call['ticker'] in ('AMD','AMAT','SNDK','ASTS'):
        extra.update(usage);extra['credit_proxy']+=credit
repairs=[]
for receipt_path in (BATCH/'adaptive').glob('*/triage_repair.receipt.json'):
    value=json.loads(receipt_path.read_text(encoding='utf-8'))
    if not value.get('usage'):continue
    initial=json.loads(receipt_path.with_name('triage.receipt.json').read_text(encoding='utf-8'))
    repairs.append({'ticker':receipt_path.parent.name,'usage':value['usage'],'web':value.get('web_search_count',0),
        'same_instructions':value['instructions_sha256']==initial['instructions_sha256'],
        'same_schema':value['schema_sha256']==initial['schema_sha256']})
no_web=[r for r in inventory['rows'] if r['web']==0]
prefix=(ROOT/'.local/codex-analysis-workspace/triage-70c17b7ab115b4cec14c92f96da83cc194869687820f823b535a6b2f7f867d63.md').read_text(encoding='utf-8')
matches=[]
for p in (ROOT/'prompts').glob('*.md'):
    text=p.read_text(encoding='utf-8')
    if len(text)>500 and text in prefix:matches.append({'path':str(p.relative_to(ROOT)),'chars':len(text),'start':prefix.index(text),'end':prefix.index(text)+len(text)})
chosen=[]
for row in sorted(matches,key=lambda r:r['chars'],reverse=True):
    if not any(row['start']<r['end'] and r['start']<row['end'] for r in chosen):chosen.append(row)
paragraphs=Counter(p.strip() for p in prefix.split('\n\n') if len(p.strip())>80)
out={'model_calls':dict(groups),'four_contract_fulls':extra,
    'no_web_reviews':{'count':len(no_web),'recorded_input_sum':sum(r['usage']['input_tokens'] for r in no_web),
        'recorded_input_median':median(r['usage']['input_tokens'] for r in no_web),
        'zero_cache_calls':sum(r['usage']['cached_input_tokens']==0 for r in no_web),
        'cached_input_sum':sum(r['usage']['cached_input_tokens'] for r in no_web)},
    'repairs':{'rows':repairs,'completed':len(repairs),'zero_cache':sum(r['usage']['cached_input_tokens']==0 for r in repairs),
        'different_schema':sum(not r['same_schema'] for r in repairs),'same_instructions':sum(r['same_instructions'] for r in repairs)},
    'prompt':{'chars':len(prefix),'components':sorted(chosen,key=lambda r:r['start']),
        'unallocated_chars':len(prefix)-sum(r['chars'] for r in chosen),
        'exact_duplicate_paragraph_upper_bound_chars':sum((n-1)*len(p) for p,n in paragraphs.items() if n>1)},
    'risk_notice':'Credit proxy uses official Standard subscription-credit rates, NOT a conversion of included weekly limits. Timeout usage unknown. Character changes not token/quality savings.'}
Path(__file__).with_name('rollup.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in out.items() if k!='repairs'},ensure_ascii=True,indent=2))
print('REPAIRS',json.dumps({k:v for k,v in out['repairs'].items() if k!='rows'}))
