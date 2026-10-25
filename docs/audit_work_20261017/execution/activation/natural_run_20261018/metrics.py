import json,hashlib,statistics
from pathlib import Path
from datetime import datetime
ROOT=Path(r'E:/stock-analysis-local')
OUT=ROOT/'.tmp/natural_run_audit_20261018'
OUT.mkdir(parents=True,exist_ok=True)
RUNS={'20261018':ROOT/'logs/batch/2026-10-18/09-08-40','20261016':ROOT/'logs/batch/2026-10-16/15-58-24'}
def j(p): return json.loads(p.read_text(encoding='utf-8-sig'))
def stats(values):
 v=sorted(values)
 return {'n':len(v),'sum':round(sum(v),3),'min':min(v) if v else None,'median':statistics.median(v) if v else None,'max':max(v) if v else None}
def dt(x): return datetime.fromisoformat(x.replace('Z','+00:00'))
result={}
for date,base in RUNS.items():
 s=j(base/'summary.json'); t=j(base/'ticker_timings.json'); source=j(base/'source_update.json')
 calls=[]; files=[]
 for p in sorted((base/'adaptive').rglob('*.receipt.json')):
  if p.parent.name in {'publish','validated_publication'}: continue
  r=j(p); call=p.with_name(p.name.replace('.receipt.json','.call.json')); c=j(call) if call.exists() else {}
  calls.append({'ticker':p.parent.name,'stage':p.name,'model':r.get('model'),'effort':r.get('reasoning_effort'),'web':r.get('web_search_count',0),'exit_code':r.get('exit_code'),'started_at':c.get('started_at'),'completed_at':r.get('completed_at'),'duration_seconds':(dt(r['completed_at'])-dt(c['started_at'])).total_seconds() if c.get('started_at') and r.get('completed_at') else None,'usage':r.get('usage'),'capacity':r.get('capacity_control'),'retryable_failure':r.get('retryable_failure')})
 ev=[]
 for c in calls:
  if c['started_at'] and c['completed_at']:
   ev += [(dt(c['started_at']),1),(dt(c['completed_at']),-1)]
 active=peak=0
 for _,change in sorted(ev): active+=change;peak=max(peak,active)
 phases={k:stats([a.get('stages_seconds',{}).get(k,0) for x in t['tickers'].values() for a in x['attempts'].values()]) for k in ['prepare','analyze','publish']}
 for f in ['summary.json','ticker_timings.json','source_update.json','pipeline_state.json','codex_budget.json']:
  p=base/f;files.append({'path':p.relative_to(ROOT).as_posix(),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
 result[date]={'batch':{k:s.get(k) for k in ['started_at','finished_at','duration_seconds','total','success','failed','retained_reports','updated_reports','regenerated_reports','retry_summary','generation_providers','model_admissions_not_started','reused_luna_verdicts','codex_fallback_tickers','measured_model_usage']},'source':{k:source.get(k) for k in ['status','started_at','finished_at','duration_seconds','exit_code']},'phase_seconds':phases,'calls':calls,'peak_overlapping_calls':peak,'model_call_seconds':stats([c['duration_seconds'] for c in calls if c['duration_seconds'] is not None]),'evidence':files}
(OUT/'metrics.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({d:{k:v for k,v in o.items() if k not in ['calls','evidence']} for d,o in result.items()},ensure_ascii=False,indent=2))
