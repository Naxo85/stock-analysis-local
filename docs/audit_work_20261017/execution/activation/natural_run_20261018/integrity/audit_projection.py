"""Read-only controller sync marker, mobile projections and one Sheets GET."""
import json,sys,hashlib,requests
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT));OUT=Path(__file__).resolve().parent;BATCH=ROOT/'logs/batch/2026-10-18/09-08-40'
from src.local_runner.publication_auth import storage_client

def load(p):return json.loads(p.read_text(encoding='utf-8'))
client=storage_client(load(ROOT/'config/codex_analysis.json')['publication_auth']);client._credentials.refresh(None)
def read(bucket,name):
 b=client.bucket(bucket).blob(name);b.reload(timeout=30);g=int(b.generation);v=b.download_as_bytes(if_generation_match=g,timeout=45);return json.loads(v),g
layout,lg=read('stock-analysis-system-naxo85','runtime/config/market_sheet_layout.json');state,sg=read(layout['analysis_sync']['mirror_bucket'],layout['analysis_sync']['mirror_prefix'].rstrip('/')+'/sync-state.json')
syms=[r['ticker'] for r in load(BATCH/'summary.json')['results']];sr=[]
for s in syms:
 commit=load(BATCH/'adaptive'/s/'publication.committed.json');sr.append({'symbol':s,'actual_version':state.get('report_generations',{}).get(s),'expected_version':commit['version'],'equal':state.get('report_generations',{}).get(s)==commit['version']})
base=ROOT/'.tmp/activation40_20261018/integrity';mobile=load(base/'stock-mobile-api-before-redacted.json')['url'];headers={'Authorization':'Bearer '+(ROOT/'.local/mobile/access-code.txt').read_text().strip()};r=requests.get(mobile+'/v1/dashboard',headers=headers,timeout=90);r.raise_for_status();d=r.json();mr=[];zones=0
for stock in d['stocks']:
 s=stock['symbol'];p=load(BATCH/'adaptive'/s/'publish/output'/s/'latest.json');expected={k:v for k,v in p['plan'].items() if k.endswith('_score') or k.endswith('_category') or k in ['entry','ambitious_entry','resistance','management_stop','structural_stop','target']};plan=stock.get('plan');zones+=sum(isinstance(plan.get(k),dict) for k in ('entry','ambitious_entry'));mr.append({'symbol':s,'plan_equal':plan==expected,'date_equal':stock.get('analysis_at')==p.get('generated_at'),'version_equal':stock.get('publication_version')==load(BATCH/'adaptive'/s/'publication.committed.json')['version'],'status':stock.get('last_attempt_status')})
# Use only the same existing OAuth credential. No scope/permission expansion.
title=layout['sheet']['title'].replace("'","''");endcol=layout['blocks'][-1]['end_column'];params={'ranges':f"'{title}'!A1:{endcol}100",'includeGridData':'true','fields':'sheets(data(startRow,startColumn,rowData(values(effectiveValue,formattedValue,hyperlink))))'}
sheet=requests.get('https://sheets.googleapis.com/v4/spreadsheets/'+layout['spreadsheet']['spreadsheet_id'],params=params,headers={'Authorization':'Bearer '+client._credentials.token},timeout=30)
sheet_result={'http_status':sheet.status_code,'read_succeeded':sheet.status_code==200}
if sheet.status_code!=200:
 try:sheet_result['error_status']=sheet.json().get('error',{}).get('status');sheet_result['error_reasons']=[x.get('reason') for x in sheet.json().get('error',{}).get('errors',[])]
 except ValueError:pass
else:
 cells={}
 for sh in sheet.json().get('sheets',[]):
  for grid in sh.get('data',[]):
   for ri,row in enumerate(grid.get('rowData',[]),grid.get('startRow',0)):
    for ci,cell in enumerate(row.get('values',[]),grid.get('startColumn',0)):cells[(ri,ci)]=cell
 def col(s):
  n=0
  for c in s:n=n*26+ord(c.upper())-64
  return n-1
 def val(c):
  v=c.get('effectiveValue',{});return v.get('numberValue',v.get('stringValue',c.get('formattedValue')))
 fields=[]
 for block in layout['blocks']:
  tc=col(block['start_column'])+layout['table_template'].get('ticker_column_offset',0);ac=col(block['start_column'])+layout['table_template'].get('analysis_start_column_offset',9)
  for ri in range(block['header_row'],block['header_row']+len(block['tickers'])):
   s=val(cells.get((ri,tc),{}))
   if s in syms:
    p=load(BATCH/'adaptive'/s/'publish/output'/s/'latest.json');version=load(BATCH/'adaptive'/s/'publication.committed.json')['version'];score=cells.get((ri,ac+3),{});fields.append({'symbol':s,'row':ri+1,'entry_display':val(cells.get((ri,ac),{})),'washout_display':val(cells.get((ri,ac+1),{})),'resistance_blank':val(cells.get((ri,ac+2),{})) in (None,''),'score_display':val(score),'score_link_version_matches':version in str(score.get('hyperlink') or ''),'score_hyperlink_present':bool(score.get('hyperlink'))})
 sheet_result['rows']=fields;sheet_result['count']=len(fields)
result={'at':datetime.now(timezone.utc).isoformat(),'controller_sync':{'generation':sg,'published_at':state.get('published_at'),'ticker_count':state.get('ticker_count'),'rows':sr,'all46versions_match':len(sr)==46 and all(x['equal'] for x in sr)},'mobile_projection':{'generated_at':d.get('generated_at'),'stale':d.get('stale'),'warnings':d.get('warnings'),'zone_count':zones,'rows':mr,'all_equal':all(x['plan_equal'] and x['date_equal'] and x['version_equal'] for x in mr)},'sheet_direct':sheet_result,'mutations':0}
(OUT/'projection_and_sheet_read.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps({'sync_all46':result['controller_sync']['all46versions_match'],'sync_at':state.get('published_at'),'mobile_all_equal':result['mobile_projection']['all_equal'],'mobile_zones':zones,'sheet_direct':sheet_result if sheet.status_code!=200 else {'http_status':200,'count':sheet_result['count']}}))
