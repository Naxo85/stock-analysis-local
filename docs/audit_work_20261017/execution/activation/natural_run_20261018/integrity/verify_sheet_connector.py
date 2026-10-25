"""Compare connector-read financial cells with the pure controller projector. No network."""
import sys,json,hashlib
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[3];sys.path[:0]=[str(ROOT),str(ROOT/'gcp_services/stock_controller/src')];OUT=Path(__file__).resolve().parent;BATCH=ROOT/'logs/batch/2026-10-18/09-08-40'
from stock_analysis.analysis_worker.reports import parse_analysis_report
from stock_analysis.controller.analysis_sheet import build_analysis_value_requests
from stock_analysis.publication_contract import with_attempt

def load(p):return json.loads(p.read_text(encoding='utf-8'))
def ci(v):
 n=0
 for x in v:n=n*26+ord(x)-64
 return n-1
def value(c):
 v=c.get('effectiveValue',{});return v.get('numberValue',v.get('stringValue',c.get('formattedValue','')))
layout=load(OUT/'sheet_projection_layout.json');raw=load(OUT/'sheet_connector_cells.json');cells={}
for sh in raw['sheets']:
 assert sh['properties']['title']=='Mercado' and sh['properties']['sheetId']==layout['sheet']['sheet_id']
 for grid in sh['data']:
  for r,row in enumerate(grid['rowData'],grid['startRow']):
   for c,cell in enumerate(row.get('values',[]),grid['startColumn']):cells[(r,c)]=cell
records={};rows={};prices={};coordinates={}
for block in layout['blocks']:
 tc=ci(block['start_column'])+layout['table_template']['ticker_column_offset'];ac=ci(block['start_column'])+layout['table_template']['analysis_start_column_offset'];block['tickers']=[]
 for r in range(block['header_row'],26):
  s=value(cells.get((r,tc),{}))
  if not s:continue
  assert isinstance(s,str) and s not in records,s
  p=load(BATCH/'adaptive'/s/'publish/output'/s/'latest.json');m=load(BATCH/'adaptive'/s/'publication.committed.json');attempt=load(BATCH/'adaptive'/s/'attempt.json');published=with_attempt(p,attempt,m)
  records[s]=parse_analysis_report(s,published,report_url_template=layout['links']['report']);rows[s]=r;prices[s]=value(cells.get((r,tc+1),{}));coordinates[(r,ac)]=s;block['tickers'].append(s)
assert len(records)==46
requests=build_analysis_value_requests(layout,records,ticker_rows=rows,prices=prices)
result=[]
for req in requests:
 u=req['updateCells'];start=u['range'];r0=start['startRowIndex'];c0=start['startColumnIndex']
 for i,row in enumerate(u['rows']):
  r=r0+i;s=coordinates[(r,c0)];checks=[]
  for j,expected in enumerate(row['values']):
   actual=cells.get((r,c0+j),{});ev=expected.get('userEnteredValue',{});v=ev.get('stringValue',ev.get('numberValue',''));av=value(actual)
   checks.append({'column_offset':j,'value_equal':str(av)==str(v),'actual_value':av,'expected_value':v,'note_equal':(actual.get('note') or '')==(expected.get('note') or '') if j in (0,1,4) else None})
  expected_url=records[s].report_url;actual_url=cells.get((r,c0+3),{}).get('hyperlink')
  result.append({'symbol':s,'row':r+1,'values_equal':all(x['value_equal'] for x in checks),'support_setup_notes_equal':all(x['note_equal'] is not False for x in checks),'versioned_link_equal':actual_url==expected_url,'versioned_link_present':bool(actual_url),'cells':checks})
output={'at':datetime.now(timezone.utc).isoformat(),'source':'Google Drive connector read; exact Mercado metadata and bounded financial cells','count':len(result),'rows':result,'values_passed':sum(x['values_equal'] for x in result),'notes_passed':sum(x['support_setup_notes_equal'] for x in result),'versioned_links_passed':sum(x['versioned_link_equal'] for x in result),'cell_values_checked':sum(len(x['cells']) for x in result),'mutations':0,'limits':['Read values, support/setup notes and score hyperlink; not cell colors, borders or physical phone.','Score note delta/history presentation not compared.','70 internal active zones does not imply70 visible cells; controller visibility threshold65 remains.']}
(OUT/'sheet_connector_verification.json').write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps({k:output[k] for k in ['count','values_passed','notes_passed','versioned_links_passed','cell_values_checked']}));print(json.dumps({'issues':[r for r in result if not (r['values_equal'] and r['support_setup_notes_equal'] and r['versioned_link_equal'])]},ensure_ascii=False))
