"""Independent offline validation of actual raw payloads against the capture module."""
import copy,datetime as dt,hashlib,json,pathlib,sys,tempfile
root=next(p for p in pathlib.Path(__file__).resolve().parents if (p/'AGENTS.md').exists() and (p/'src').is_dir());sys.path.insert(0,str(root))
from src.local_runner import ibkr_news_capture as c
(root/'.tmp/news_capture_reuse_recheck').mkdir(parents=True,exist_ok=True)
inventory=json.loads((root/'docs/audit_work_20261017/execution/activation/natural_run_20261018/data/raw_acquisitions.json').read_text())
out=root/'.tmp/news_capture_reuse_recheck'
rows=[];fetches=[]
with tempfile.TemporaryDirectory() as td:
 for item in sorted(inventory,key=lambda x:x['generated_at']):
  path=root/item['path'];p=json.loads(path.read_text(encoding='utf-8'));now=dt.datetime.fromisoformat(p['generated_at'])+dt.timedelta(seconds=1)
  identity=c._identity(p['ticker'],p['providerCode'],p['contract'],p['connection'])
  c._validate_payload(p,identity)
  def fetch(p=p):
   fetches.append((p['ticker'],p['providerCode']));return p
  cap=c.get_or_create_capture(pathlib.Path(td),symbol=p['ticker'],provider=p['providerCode'],contract=p['contract'],connection=p['connection'],fetch=fetch,now=now,max_age_seconds=86400)
  derived=c.derive_probe_payload(cap,start=dt.datetime.fromisoformat(p['window']['start']),window_basis=p['window']['basis'],earnings_context=p.get('earnings_context'),now=now,max_age_seconds=86400)
  checks={
   'headlines_exact':derived['headlines']==p['headlines'],
   'raw_exact':derived['raw_headlines']==p['raw_headlines'],
   'window_start_exact':derived['window']['start']==p['window']['start'],
   'coverage_original_preserved':derived['coverage']==cap['payload']['coverage'],
   'generated_at_original_preserved':derived['generated_at']==cap['payload']['generated_at'],
   'end_original_preserved':derived['window']['end']==cap['payload']['window']['end'],
   'provider_fetched_original_preserved':derived['provider_fetched_at']==cap['payload']['generated_at'],
  }
  rows.append({'path':item['path'],'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'ticker':p['ticker'],'provider':p['providerCode'],'checks':checks,'capture_sha256':cap['capture_sha256']})
  assert all(checks.values()),rows[-1]
result={'status':'passed','raw_payloads_validated':len(rows),'derived_views_checked':len(rows),'capture_callbacks':len(fetches),'distinct_ticker_provider':len(set(fetches)),'historical_artifacts_read_only':True,'network_or_models':False,'checks':rows,'limits':'Sunday static cache corpus; does not prove equivalence across changing live cutoffs or wall-clock savings.'}
(out/'independent_historical_core.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k!='checks'},indent=2))
