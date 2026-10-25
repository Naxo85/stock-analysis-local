"""GET-only check of compatibility mirrors and batch status objects."""
import json,sys,hashlib
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT));OUT=Path(__file__).resolve().parent;BATCH=ROOT/'logs/batch/2026-10-18/09-08-40'
from src.local_runner.publication_auth import storage_client

def load(p):return json.loads(p.read_text(encoding='utf-8'))
client=storage_client(load(ROOT/'config/codex_analysis.json')['publication_auth']);client._credentials.refresh(None)
def read(bucket,name):
 b=client.bucket(bucket).blob(name);b.reload(timeout=30);g=int(b.generation);v=b.download_as_bytes(if_generation_match=g,timeout=45);return v,g
symbols=[r['ticker'] for r in load(BATCH/'summary.json')['results']]
def one(s):
 try:
  raw,g=read('stock-analysis-system-naxo85','runtime/analysis-reports/'+s+'.json');m=json.loads(raw);local=load(BATCH/'adaptive'/s/'publish/output'/s/'latest.json');assert m==local,'mirror_payload_mismatch'
  return {'symbol':s,'passed':True,'generation':g,'sha256':hashlib.sha256(raw).hexdigest(),'financial_date':m.get('generated_at')}
 except Exception as e:return {'symbol':s,'passed':False,'error':str(e),'type':type(e).__name__}
with ThreadPoolExecutor(max_workers=6) as p:rows=list(p.map(one,symbols))
metadata=[]
for bucket,name,file in [('stock-analysis-system-naxo85','runtime/analysis-status/latest_trading.json','sheet_status.json'),('stock-analysis-reports-naxo85','batch/status/latest_trading.json','summary.json')]:
 try:
  raw,g=read(bucket,name);same=json.loads(raw)==load(BATCH/file);metadata.append({'bucket':bucket,'name':name,'local_file':file,'generation':g,'exact_payload':same,'sha256':hashlib.sha256(raw).hexdigest()})
 except Exception as e:metadata.append({'name':name,'error':str(e),'type':type(e).__name__})
result={'at':datetime.now(timezone.utc).isoformat(),'mirrors_passed':sum(r['passed'] for r in rows),'count':len(rows),'rows':rows,'metadata':metadata,'mutations':0,'limit':'GCS compatibility/Sheet input mirror only; actual Sheet cells not read or changed.'}
(OUT/'compatibility_mirrors.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps({'mirrors_passed':result['mirrors_passed'],'count':len(rows),'metadata':metadata,'errors':[r for r in rows if not r['passed']]}))
