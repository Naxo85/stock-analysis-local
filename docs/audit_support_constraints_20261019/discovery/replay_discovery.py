"""Read-only replay of the 18-Oct capture; output only under this audit directory.

No imports of producer module top-level, network, models or production changes.
Only literal selected function definitions are loaded from the working source.
The source functions' datetime clock is frozen to each captured as_of.
"""
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter
import ast
import hashlib
import json
import math
import statistics

ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent
RAW=ROOT/'gcp_functions/support_resistances_raw/main.py'
BATCH=ROOT/'logs/batch/2026-10-18/09-08-40/adaptive'
NAMES={'_to_float','_median','_atr10_from_daily','_find_52w_low',
 '_find_swing_lows','_cluster_swing_lows','_select_range_bottom_cluster',
 '_find_bullish_gaps','_select_bullish_gap_support','_select_avwap_event_support',
 '_avwap_from_date','_volume_on_date','_first_trading_day_of_year','_is_testing_now'}
tree=ast.parse(RAW.read_text(encoding='utf-8'))
nodes=[node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name in NAMES]
assert {node.name for node in nodes}==NAMES
ns={'math':math,'statistics':statistics,'datetime':datetime}
exec(compile(ast.Module(body=nodes,type_ignores=[]),str(RAW),'exec'),ns)

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path):return json.loads(path.read_text(encoding='utf-8-sig'))
def rounded(x):return round(x,4) if x is not None else None
def selection(row,price):
 if row is None:return None
 row=dict(row)
 row['level']=rounded(row['level'])
 row['distance_below_pct']=round(100*(price-row['level'])/price,6)
 return row
def level_matches(a,b):
 return (a is None and b is None) or bool(a and b and rounded(a['level'])==rounded(b['level']))

def typed_references(value):
 found=[]
 if isinstance(value,dict):
  if value.get('type') in ['range_bottom_3_6m','gap_up_lower']:
   found.append(value)
  for child in value.values():found.extend(typed_references(child))
 elif isinstance(value,list):
  for child in value:found.extend(typed_references(child))
 return found

results=[]; hashes={str(RAW.relative_to(ROOT)):digest(RAW)}
for input_path in sorted(BATCH.glob('*/input.json')):
 inp=read(input_path); slim=inp['slim']; symbol=inp['symbol']; snap=slim['as_of']
 archives=[(p,read(p)) for p in (ROOT/'data/technical_archive'/symbol).glob('*.json')]
 matches=[(p,d) for p,d in archives if d.get('snapshot_at')==snap and d.get('symbol')==symbol]
 assert len(matches)==1,(symbol,snap,len(matches))
 archive_path,archive=matches[0]
 assert archive['origin']=='prospective_raw_capture'
 assert archive['source_revision']==slim['data_contract_revision']==40
 coverage=archive['daily']['coverage']
 if not coverage['window_complete']:print('INCOMPLETE_WINDOW',symbol,'invalid_row_indexes',coverage['invalid_row_indexes'],'missing_expected_sessions_count',len(coverage['missing_expected_sessions']))
 assert not coverage['incomplete_or_future_row_indexes']
 # Preserve raw historical rows exactly to replay what production selected.
 # Archive quality flags remain explicit; no inference of complete history.
 days=archive['daily']['rows']
 assert all(d['date']<=snap[:10] for d in days)
 assert days[-1]['date']=='2026-10-16'
 frozen=datetime.fromisoformat(snap).replace(tzinfo=None)
 class FrozenClock(datetime):
  @classmethod
  def utcnow(cls):return frozen
 ns['datetime']=FrozenClock
 price=slim['latest_price'];atr=ns['_atr10_from_daily'](days)
 assert round(atr,4)==round(slim['technicals']['atr10'],4)
 tol=.2*atr
 assert tol>0
 win=days[-126:]; gap_days=days[-252:]
 lows=ns['_find_swing_lows'](win,k=2)
 clusters=ns['_cluster_swing_lows'](lows,tol)
 gaps=ns['_find_bullish_gaps'](gap_days)
 vol=ns['_median']([x['volume'] for x in win])
 low52,date52=ns['_find_52w_low'](days,252)
 originals={r['type']:r for r in slim['levels']['supports']}
 picks={}
 for threshold in [.05,0.0]:
  picks[threshold]={
   'range_bottom_3_6m':ns['_select_range_bottom_cluster'](clusters,price,None,tol,vol,threshold),
   'gap_up_lower':ns['_select_bullish_gap_support'](gaps,gap_days,price,None,tol,threshold),
   'avwap_event_support':ns['_select_avwap_event_support'](days,gap_days,gaps,atr,price,tol,date52,clusters,vol,threshold,1.5,.5,None)}
 lanes=[]
 for family in ['supports','observed_origins','put_walls_top','option_origins']:
  for row in slim['levels'].get(family,[]):
   if isinstance(row.get('level'),(float,int)):
    lanes.append({'lane':family,'type':row.get('type'),'level':row['level'],'date':row.get('date'),'status':row.get('status')})
 for key in ['sma20','sma50','sma200','donchian20_low','keltner_lower']:
  value=slim['technicals'].get(key)
  if isinstance(value,(float,int)):lanes.append({'lane':'technicals','type':key,'level':value})
 comparisons=[]
 for family in picks[.05]:
  before=picks[.05][family]; after=picks[0.0][family]; original=originals.get(family)
  assert level_matches(before,original),(symbol,family,before,original)
  comparison={'type':family,'original_level':original.get('level') if original else None,
   'baseline':selection(before,price),'without_5pct':selection(after,price),'changed':not level_matches(before,after)}
  if after is not None:
   candidate=after['level']
   comparison['same_coordinate_other_lane']=[r for r in lanes if abs(r['level']-candidate)<=.0001]
   comparison['nearby_within_0_2_atr']=[{**r,'distance_atr':round(abs(r['level']-candidate)/atr,6)} for r in lanes if abs(r['level']-candidate)<=.2*atr]
   comparison['in_primary_reach_atr_or_em']= bool((price-candidate)<=atr or (price-candidate)<=(slim['options'].get('expected_move_1w_abs') or 0))
  comparisons.append(comparison)
 masked_ranges=[dict(r) for r in clusters if r['touches']>=2 and price*.95<r['level']<=price]
 masked_gaps=[dict(r) for r in gaps if price*.95<r['lower']<=price]
 near_lanes=[{**r,'distance_below_pct':round(100*(price-r['level'])/price,6)} for r in lanes if price*.95<r['level']<=price]
 targeted=[]
 plan=inp['reference'].get('semantic_report',{}).get('data',{}).get('plan',{})
 for slot in ['entry','ambitious_entry']:
  zone=plan.get(slot) or {}
  if not zone.get('range'):continue
  refs=typed_references(zone.get('resolved_facts'))+typed_references((zone.get('support_validity') or {}).get('sources'))
  seen=set()
  for old in refs:
   key=(old.get('type'),old.get('level'),old.get('date'),old.get('touches'))
   if key in seen:continue
   seen.add(key)
   if old['type']=='range_bottom_3_6m':
    candidates=[c for c in clusters if rounded(c['level'])==old.get('level') and c['last_date']==old.get('date') and c['touches']==old.get('touches')]
   else:
    candidates=[c for c in gaps if rounded(c['lower'])==old.get('level') and c['date']==old.get('date')]
   live=originals.get(old['type'])
   in_selected=bool(live and live.get('level')==old.get('level') and live.get('date')==old.get('date'))
   targeted.append({'slot':slot,'prior_identity':dict(zip(['type','level','date','touches'],key)),
    'selected_in_current_slim':in_selected,'exact_current_pool_match_count':len(candidates),
    'matches':candidates,'scope':'Typed records associated with active CURRENT zone, not inferred defining origin; metadata must match exactly.'})
 results.append({'symbol':symbol,'snapshot_at':snap,'archive':str(archive_path.relative_to(ROOT)),'input':str(input_path.relative_to(ROOT)),
  'history_rows':len(days),'first_session':days[0]['date'],'last_session':days[-1]['date'],'history_window_complete':coverage['window_complete'],
  'history_quality_flags':{k:coverage[k] for k in ['invalid_row_indexes','missing_expected_sessions']},
  'price':price,'atr10':atr,'atr10_pct':100*atr/price,'em1w_abs':slim['options'].get('expected_move_1w_abs'),
  'baseline_matches_original':True,'comparisons':comparisons,
  'masked_range_pool':masked_ranges,'masked_gap_pool':masked_gaps,'existing_near_lanes':near_lanes,
  'targeted_current_origin_check':targeted,
  'current_financial_ranges':{k:inp['reference'].get('plan',{}).get(k) for k in ['entry','ambitious_entry']}})
 for p in [input_path,archive_path]:hashes[str(p.relative_to(ROOT))]=digest(p)

changed=[(r,c) for r in results for c in r['comparisons'] if c['changed']]
def count_families(rows):return dict(Counter(c['type'] for r,c in rows))
summary={
 'tickers':len(results),'exact_archive_timestamp_matches':len(results),'baseline_level_matches':3*len(results),
 'source_sha256':digest(RAW),
 'baseline_candidates':sum(c['baseline'] is not None for r in results for c in r['comparisons']),
 'without_5pct_candidates':sum(c['without_5pct'] is not None for r in results for c in r['comparisons']),
 'changed_selections':len(changed),'changed_tickers':sorted({r['symbol'] for r,c in changed}),
 'changed_by_family':count_families(changed),
 'new_nonempty':sum(c['baseline'] is None for r,c in changed),
 'replacements':sum(c['baseline'] is not None for r,c in changed),
 'changed_same_coordinate_other_lane':sum(bool(c.get('same_coordinate_other_lane')) for r,c in changed),
 'changed_with_any_lane_within_0_2_atr':sum(bool(c.get('nearby_within_0_2_atr')) for r,c in changed),
 'changed_primary_reach_atr_or_em':sum(c.get('in_primary_reach_atr_or_em',False) for r,c in changed),
 'masked_range_pool':sum(len(r['masked_range_pool']) for r in results),
 'masked_gap_pool':sum(len(r['masked_gap_pool']) for r in results),
 'tickers_with_any_near_lane':sum(bool(r['existing_near_lanes']) for r in results),
 'near_lanes_by_type':dict(Counter(x['lane']+':'+str(x['type']) for r in results for x in r['existing_near_lanes'])),
 'atr10_below_5pct_tickers':sum(r['atr10_pct']<5 for r in results),
 'history_window_complete_tickers':sum(r['history_window_complete'] for r in results),
 'history_window_incomplete_tickers':[r['symbol'] for r in results if not r['history_window_complete']],
 'changed_in_history_complete_tickers':sum(r['history_window_complete'] for r,c in changed),
 'active_current_typed_origin_requests':sum(len(r['targeted_current_origin_check']) for r in results),
 'active_current_unique_typed_origins':len({(r['symbol'],json.dumps(t['prior_identity'],sort_keys=True)) for r in results for t in r['targeted_current_origin_check']}),
 'active_origin_omitted_but_exactly_reproducible':sum(not t['selected_in_current_slim'] and t['exact_current_pool_match_count']==1 for r in results for t in r['targeted_current_origin_check']),
 'active_origin_omitted_tickers':sorted({r['symbol'] for r in results for t in r['targeted_current_origin_check'] if not t['selected_in_current_slim'] and t['exact_current_pool_match_count']==1}),
}
assert len(results)==46
for path,sha in hashes.items():assert digest(ROOT/path)==sha
payload={'scope':'18Oct frozen same-capture offline sensitivity; selectors unchanged except distance threshold; no outcome or financial rescoring',
 'method':{'clock':'snapshot_at','windows':'126 swing and 252 gap sessions, original raw logic','today_low':None,
  'today_low_limit':'Not supplied: affects testing_now only, not selected coordinates; coordinate baseline verified against all original selections.',
  'avwap':'Original anchor priority retained; this is not an exhaustive AVWAP inventory.',
  'future_data':'19Oct archives excluded; original snapshots include bars only through16Oct.',
  'unchanged_financial_policy':'No inferred viability, scores, visibility or performance from candidate counts.'},
 'summary':summary,'inputs_sha256':hashes,'results':results}
(OUT/'discovery_replay.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False,indent=2))
for r,c in changed:
 print(r['symbol'],c['type'],c['baseline']['level'] if c['baseline'] else None,'->',c['without_5pct']['level'],
  'distance',c['without_5pct']['distance_below_pct'],'exact lanes',len(c.get('same_coordinate_other_lane',[])),
  'near lanes',[(x['lane'],x['type'],x['level']) for x in c.get('nearby_within_0_2_atr',[])])
