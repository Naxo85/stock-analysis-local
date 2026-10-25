"""Offline context budget and overlap audit on unchanged archived inputs."""
import json, pathlib, sys, statistics
from datetime import date, timedelta
ROOT=pathlib.Path.cwd();sys.path.insert(0,str(ROOT));OUT=ROOT/'.tmp/audit_execution_20261017'
from gcp_functions.support_resistances_raw.price_path import horizontal_path_evidence
from gcp_functions.support_resistances_raw.market_sessions import market_session
def size(x):return len(json.dumps(x,ensure_ascii=False,separators=(',',':')).encode('utf8'))
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
rows=read(OUT/'candidate_comparison.json');actual=[];identity=set();all_events=0
for r in rows:
 if r['day']<'2026-10-13' or not r['baseline']:continue
 d=read(ROOT/r['path']);bars=(d['slim'].get('price_history')or{}).get('sessions')or[]
 if not bars:continue
 level=r['baseline'][0]['level'];tol=.2*r['atr'] if r['atr'] else 0
 full=horizontal_path_evidence(level,bars,tol,max_events=8);bounded=horizontal_path_evidence(level,bars,tol)
 for e in full.get('events',[]):
  identity.add((r['symbol'],level,e['contact_date'],e['window_end']));all_events+=1
 actual.append({'symbol':r['symbol'],'day':r['day'],'completed_count':full['completed_count'],'bytes_8':size(full),'bytes_3':size(bounded),'events_8':len(full['events']),'events_3':len(bounded['events'])})
bars=[];day=date(2025,1,1)
while len(bars)<252:
 if market_session(day):
  i=len(bars);lo,hi,close=(99,101,100)if i%2==0 else (102,105,104)
  bars.append(dict(date=day.isoformat(),low=lo,high=hi,close=close))
 day+=timedelta(days=1)
full=horizontal_path_evidence(100,bars,0,max_events=8);bounded=horizontal_path_evidence(100,bars,0)
summary={'actual_coordinates':len(actual),'actual_more_than_three_complete':sum(r['completed_count']>3 for r in actual),'actual_detail_rows_8':all_events,'actual_detail_rows_3':sum(r['events_3']for r in actual),'unique_symbol_coordinate_contact_window':len(identity),'actual_median_bytes_8':statistics.median(r['bytes_8']for r in actual),'actual_median_bytes_3':statistics.median(r['bytes_3']for r in actual),'actual_total_bytes_saved':sum(r['bytes_8']-r['bytes_3']for r in actual),'synthetic_252_sessions':{'completed_count':full['completed_count'],'pending_count':full['pending_count'],'bytes_8':size(full),'bytes_3':size(bounded),'bytes_saved':size(full)-size(bounded),'relative_reduction':1-size(bounded)/size(full)},'limits':['UTF-8 compact JSON bytes, not exact model tokens','Synthetic alternating contacts test the detail budget; not empirical frequency or financial validity','Repeated coordinates and windows across snapshots are not independent trials','All counter, adverse extreme and median summaries use all complete contacts regardless of detail budget']}
(OUT/'path_context_budget.json').write_text(json.dumps({'summary':summary,'observations':actual,'synthetic_8':full,'synthetic_3':bounded},indent=2),encoding='utf8');print(json.dumps(summary,indent=2))
