"""Read-only audit of one completed natural batch. Only GET/download remote calls."""
import hashlib,json,sys,os
from pathlib import Path
from datetime import datetime,timezone
from concurrent.futures import ThreadPoolExecutor
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
BATCH=ROOT/'logs/batch/2026-10-18/09-08-40';OUT=Path(__file__).resolve().parent
from src.local_runner.publication_bundle import verify_bundle
from src.local_runner.receipt_integrity import authenticate_response
from src.local_runner.publication_contract import validate_manifest,verify_artifact,digest_json,digest_text
from src.local_runner.adaptive_cache import reference_key
from src.local_runner.publication_auth import storage_client
from src.local_runner.codex_call_evidence import inspect as inspect_call

def load(p):return json.loads(p.read_text(encoding='utf-8'))
def save(n,v):(OUT/n).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def sha(b):return hashlib.sha256(b).hexdigest()
def check(value,label):
 if not value:raise AssertionError(label)
SUMMARY=load(BATCH/'summary.json');SYMS=[x['ticker'] for x in SUMMARY['results']]
def local_one(s):
 w=BATCH/'adaptive'/s;c=load(w/'input.json');r=load(w/'review.json');p=load(w/'policy.json');m,a,e=verify_bundle(w,s,r,return_artifacts=True)
 commit=validate_manifest(load(w/'publication.committed.json'),s);attempt=load(w/'attempt.json');payload=json.loads(a['latest.json']);anchor=load(w/'publish/anchor_state.json');current=load(w/'publish/current_state.json')
 check(commit['committed_at']==r['published_at'],'commit_time');check(attempt['status']=='succeeded' and attempt['committed_version']==commit['version'],'attempt_commit')
 check(c['routing_revision']==r['routing_revision']==p['routing_revision']==40,'revision40')
 check(reference_key(c['reference'])==r['base_report_sha256'],'base_hash');check(reference_key(c['sol_reference'])==r['sol_anchor_sha256'],'anchor_hash')
 receipts=[]
 for receiptfile in sorted(w.glob('*.receipt.json')):
  kind=receiptfile.name[:-len('.receipt.json')];rec=load(receiptfile)
  response=authenticate_response(w,kind,rec);events=(w/(kind+'.events.jsonl')).read_text(encoding='utf-8')
  check(inspect_call(events,response)['state']=='completed',kind+':event_completion')
  check(sha((w/(kind+'.input.json')).read_bytes())==rec['input_sha256'],kind+':input_bytes')
  schema=load(w/(kind+'.schema.json'));check(sha(json.dumps(schema,sort_keys=True).encode())==rec['schema_sha256'],kind+':schema')
  receipts.append({'kind':kind,'input_hash':True,'response_events_call_authenticated':True,'event_completed':True,'schema_hash':True})
 check(r['status']=='regenerated' or anchor==c['sol_reference'],'exact_anchor_preserved')
 check(current['sol_anchor_sha256']==reference_key(anchor),'current_anchor_binding')
 check(current['last_full_report_at']==anchor.get('generated_at')==r['last_full_report_at'],'full_date_binding')
 snapshot=w/'validated_publication'/r['bundle_manifest_sha256']/'output'/s
 for name,text in a.items():check((snapshot/name).read_text(encoding='utf-8')==text,'snapshot:'+name)
 changed=[key for key in sorted(set(payload)|set(c['reference'])) if payload.get(key)!=c['reference'].get(key)]
 if r['status']=='retained':check(payload['generated_at']==c['reference']['generated_at'],'retained_financial_date')
 return {'symbol':s,'status':r['status'],'presentation_changed':r.get('presentation_changed'),'bundle_passed':True,'receipts':receipts,'version':commit['version'],'committed_at':commit['committed_at'],'attempt_succeeded':True,'anchor_exactly_preserved':anchor==c['sol_reference'],'last_full_report_at':r['last_full_report_at'],'financial_date':payload.get('generated_at'),'previous_financial_date':c['reference'].get('generated_at'),'retained_date_equal':payload.get('generated_at')==c['reference'].get('generated_at') if r['status']=='retained' else None,'changed_top_level_keys':changed,'retained_decision_exact':payload.get('decision')==c['reference'].get('decision') if r['status']=='retained' else None,'retained_plan_exact':payload.get('plan')==c['reference'].get('plan') if r['status']=='retained' else None,'retained_catalysts_exact':payload.get('catalysts')==c['reference'].get('catalysts') if r['status']=='retained' else None,'retained_next_event_exact':payload.get('next_event')==c['reference'].get('next_event') if r['status']=='retained' else None,'snapshots_passed':True}

def main(remote=False):
 rows=[]
 for s in SYMS:
  try:rows.append(local_one(s))
  except Exception as exc:rows.append({'symbol':s,'error':str(exc),'type':type(exc).__name__})
 result={'at':datetime.now(timezone.utc).isoformat(),'batch':str(BATCH.relative_to(ROOT)),'local_passed':sum('error' not in r for r in rows),'count':len(rows),'rows':rows,'sheet_status_local':load(BATCH/'sheet_status.json'),'scope':'Read-only original artifacts; no model or publication call'}
 save('local_integrity.json',result);print(json.dumps({'local_passed':result['local_passed'],'count':len(rows),'errors':[r for r in rows if 'error' in r]}),flush=True)
 if not remote:return
 import requests
 client=storage_client(load(ROOT/'config/codex_analysis.json')['publication_auth']);client._credentials.refresh(None);bucket=client.bucket('stock-analysis-reports-naxo85')
 base=ROOT/'.tmp/activation40_20261018/integrity'
 web=load(base/'reports-before-redacted.json')['url'];mobile=load(base/'stock-mobile-api-before-redacted.json')['url'];headers={'Authorization':'Bearer '+(ROOT/'.local/mobile/access-code.txt').read_text().strip()}
 def read(name):
  b=bucket.blob(name);b.reload(timeout=30);g=int(b.generation);body=b.download_as_bytes(if_generation_match=g,timeout=45);return body,g
 def remote_one(s):
  try:
   w=BATCH/'adaptive'/s;lc=load(w/'publication.committed.json');raw,g=read(s+'/publication.json');m=validate_manifest(json.loads(raw),s);check(m==lc,'remote_manifest_vs_local_commit');check(m.get('committed_at'),'commit_confirmed')
   artifacts={};checks=[]
   for kind,item in m['files'].items():
    body,bg=read(item['name']);check(sha(body)==item['sha256'],'immutable_hash:'+kind);verify_artifact(m,kind,body.decode('utf-8'));artifacts[kind]=body;checks.append({'kind':kind,'generation':bg,'sha256':sha(body)})
   history,hg=read(s+'/_versions/'+m['version']+'/manifest.json');check(json.loads(history)==m,'historical_manifest')
   attempt,ag=read(s+'/attempt.json');at=json.loads(attempt);check(at==load(w/'attempt.json'),'remote_attempt_vs_local');check(at['status']=='succeeded' and at['committed_version']==m['version'],'attempt_version')
   p=json.loads(artifacts['json']);anchor=json.loads(artifacts['anchor']);check(anchor==load(w/'input.json')['sol_reference'],'remote_anchor_exact')
   local={'json':w/'publish/output'/s/'latest.json','md':w/'publish/output'/s/'latest.md','html':w/'publish/output'/s/'latest.html','anchor':w/'publish/anchor_state.json','current':w/'publish/current_state.json'}
   for kind,path in local.items():
    text=path.read_text(encoding='utf-8');check(text==artifacts[kind].decode('utf-8') if kind in ('json','md','html') else json.loads(text)==json.loads(artifacts[kind]),'local_vs_remote:'+kind)
   pr=requests.get(web,params={'symbol':s,'debug':'true'},timeout=90);pr.raise_for_status();pp=pr.json();mr=requests.get(mobile+'/v1/reports/'+s,headers=headers,timeout=90);mr.raise_for_status();mp=mr.json()
   for reader,public in [('web',pp),('mobile',mp)]:
    for key in ('generated_at','analysis_markdown','analysis_status'):check(public.get(key)==p.get(key),reader+':'+key)
    check(public.get('publication_version')==m['version'],reader+':version');check((public.get('latest_attempt') or {}).get('status')=='succeeded',reader+':attempt')
   # An explicit historic version must resolve the exact committed body.
   vr=requests.get(web,params={'symbol':s,'debug':'true','version':m['version']},timeout=90);vr.raise_for_status();vp=vr.json();check(vp.get('publication_version')==m['version'] and vp.get('analysis_markdown')==p.get('analysis_markdown'),'versioned_link')
   again,again_g=read(s+'/publication.json');check(again_g==g and again==raw,'authority_changed_during_read')
   return {'symbol':s,'passed':True,'version':m['version'],'manifest_generation':g,'historical_manifest_generation':hg,'attempt_generation':ag,'attempt_status':at['status'],'objects':checks,'web_equal':True,'mobile_equal':True,'versioned_web_link_equal':True,'anchor_exact':True,'financial_date':p.get('generated_at'),'manifest_unchanged_during_check':True,'markdown_sha256':sha(p.get('analysis_markdown','').encode())}
  except Exception as exc:return {'symbol':s,'passed':False,'error':str(exc),'type':type(exc).__name__}
 with ThreadPoolExecutor(max_workers=6) as pool:
  rr=[]
  for row in pool.map(remote_one,SYMS):
   rr.append(row);save('remote_progress.json',rr);print(json.dumps({'remote_symbol':row['symbol'],'passed':row['passed'],'error':row.get('error')}),flush=True)
 dash=requests.get(mobile+'/v1/dashboard',headers=headers,timeout=90);dash.raise_for_status();dp=dash.json();stocks=dp['stocks'];drows=[]
 for stock in stocks:
  s=stock.get('symbol');local=next((r for r in rows if r['symbol']==s),None)
  if local:drows.append({'symbol':s,'financial_date_equal':stock.get('analysis_at')==local.get('financial_date'),'last_attempt_status':stock.get('last_attempt_status'),'publication_version':stock.get('publication_version'),'keys':sorted(stock.keys())})
 save('remote_integrity.json',{'at':datetime.now(timezone.utc).isoformat(),'passed':all(r['passed'] for r in rr),'count':len(rr),'rows':rr,'dashboard':{'count':len(stocks),'warnings':dp.get('warnings'),'stale':dp.get('stale'),'rows':drows},'mutations':0,'model_calls':0,'scope':'Authenticated GCS downloads and consumer GETs; no remote mutations'})
 print(json.dumps({'remote_passed':sum(r['passed'] for r in rr),'count':len(rr),'dashboard_warnings':len(dp.get('warnings',[]))}),flush=True)
if __name__=='__main__':main('--remote' in sys.argv)
