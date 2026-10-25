import json,hashlib,copy,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from src.local_runner.review_contract import reconcile_plan_explanation
RUN=ROOT/'logs/batch/2026-10-18/09-08-40/adaptive'
rows=[]
for base in sorted(RUN.iterdir()):
    response=json.loads((base/'triage.json').read_text(encoding='utf-8'))
    if response['decision']!='update': continue
    change=response['update']
    if change['plan_explanation'] is not None: continue
    inp=json.loads((base/'input.json').read_text(encoding='utf-8'))
    current=json.loads((base/'publish/current_state.json').read_text(encoding='utf-8'))
    old=inp['reference']['semantic_report']['data']['plan']
    doc=current['semantic_report']['data']
    changed=any(doc['plan'][k]['range']!=v['range'] for k,v in old.items())
    results={str(rev):reconcile_plan_explanation(copy.deepcopy(doc),copy.deepcopy(change),copy.deepcopy(old),{'routing_revision':rev}) for rev in (39,40)}
    rows.append({'symbol':base.name,'changed_ranges':changed,'plan_explanation':None,'isolated_guard_issues':results,'response_sha256':hashlib.sha256((base/'triage.json').read_bytes()).hexdigest()})
result={'scope':'Isolated coherence certificate guard only. Exact natural responses and resulting ranges; revision selects this single guard branch, not old admission, prompts, financial validation or model behavior. No historical files changed.','old_rejections':sum(bool(r['isolated_guard_issues']['39']) for r in rows),'new_rejections':sum(bool(r['isolated_guard_issues']['40']) for r in rows),'null_update_responses':len(rows),'rows':rows,'code_sha256':hashlib.sha256((ROOT/'src/local_runner/review_contract.py').read_bytes()).hexdigest()}
Path(__file__).with_suffix('.json').write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8')
print(json.dumps({k:result[k] for k in ('old_rejections','new_rejections','null_update_responses')}))
