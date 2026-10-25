"""Predeclared exploratory distance control on frozen one-session candidates.
No providers, models, operational imports, source mutations or new future labels.
"""
import collections, functools, hashlib, json, math, pathlib, statistics
ROOT=pathlib.Path.cwd();OUT=ROOT/'.tmp/audit_execution_20261017'
def load(name):return json.loads((OUT/name).read_text(encoding='utf-8-sig'))
def med(values):return statistics.median(values) if values else None
def rate(values):return sum(values)/len(values) if values else None
def identity(row):return round(row['level'],6)
def group_index(distance):
 for i,(lo,hi)in enumerate(zip(design['bins_pct'],design['bins_pct'][1:])):
  if distance>=lo and(hi is None or distance<hi):return i
 raise AssertionError('distance outside predeclared bins')
def match(a,b):
 # Selection uses distances only. Outcomes are read only after assignment.
 @functools.lru_cache(None)
 def solve(i,used):
  if i==len(a):return ()
  choices=[solve(i+1,used)]
  for j in range(len(b)):
   if not used&(1<<j) and abs(a[i]['distance_pct']-b[j]['distance_pct'])<=design['primary_caliper_percentage_points']+1e-12:
    choices.append(((i,j),)+solve(i+1,used|(1<<j)))
  return min(choices,key=lambda pairs:(-len(pairs),sum(abs(a[x]['distance_pct']-b[y]['distance_pct'])for x,y in pairs),pairs))
 return solve(0,0)
def summary_pairs(pairs):
 states=collections.Counter(('both'if p['baseline']['touched']and p['alternative']['touched']else'baseline_only'if p['baseline']['touched']else'alternative_only'if p['alternative']['touched']else'neither')for p in pairs)
 return {'pairs':len(pairs),'contexts':len({(p['symbol'],p['day'])for p in pairs}),'dates':sorted({p['day']for p in pairs}),
  'baseline_touched':sum(p['baseline']['touched']for p in pairs),'alternative_touched':sum(p['alternative']['touched']for p in pairs),
  'baseline_touch_rate':rate([p['baseline']['touched']for p in pairs]),'alternative_touch_rate':rate([p['alternative']['touched']for p in pairs]),
  'paired_difference_alternative_minus_baseline':rate([int(p['alternative']['touched'])-int(p['baseline']['touched'])for p in pairs]),
  'discordance':dict(states),'median_abs_distance_difference_pp':med([p['distance_difference_pp']for p in pairs]),
  'median_abs_distance_difference_ATR':med([p['distance_difference_ATR']for p in pairs if p['distance_difference_ATR']is not None]),
  'median_baseline_distance_pct':med([p['baseline']['distance_pct']for p in pairs]),'median_alternative_distance_pct':med([p['alternative']['distance_pct']for p in pairs]),
  'per_date':{day:{'pairs':sum(p['day']==day for p in pairs),'baseline_touched':sum(p['baseline']['touched']for p in pairs if p['day']==day),'alternative_touched':sum(p['alternative']['touched']for p in pairs if p['day']==day)}for day in sorted({p['day']for p in pairs})}}
def strata(contexts):
 pooled=[];cells=[]
 for i,(lo,hi)in enumerate(zip(design['bins_pct'],design['bins_pct'][1:])):
  arm_rows={arm:[c for r in contexts for c in r[arm] if group_index(c['distance_pct'])==i]for arm in ('baseline','alternative')}
  pooled.append({'bin':i,'lower_pct':lo,'upper_exclusive_pct':hi,**{arm:{'candidates':len(cs),'touched':sum(c['touched']for c in cs),'touch_rate':rate([c['touched']for c in cs]),'median_distance_pct':med([c['distance_pct']for c in cs])}for arm,cs in arm_rows.items()}})
  for r in contexts:
   aa={arm:[c for c in r[arm] if group_index(c['distance_pct'])==i]for arm in ('baseline','alternative')}
   if not any(aa.values()):continue
   weight=min(len(aa['baseline']),len(aa['alternative']))
   cells.append({'symbol':r['symbol'],'day':r['day'],'bin':i,'weight':weight,**{arm:{'n':len(cs),'touched':sum(c['touched']for c in cs),'rate':rate([c['touched']for c in cs]),'mean_distance_pct':statistics.mean(c['distance_pct']for c in cs)if cs else None}for arm,cs in aa.items()}})
 comparable=[c for c in cells if c['weight']];w=sum(c['weight']for c in comparable)
 standardized={arm:sum(c['weight']*c[arm]['rate']for c in comparable)/w if w else None for arm in ('baseline','alternative')}
 return {'pooled_bins':pooled,'within_context_common_cells':len(comparable),'within_context_one_arm_only_cells':sum(not c['weight']for c in cells),'common_cell_weight':w,'standardized_touch_rates':standardized,'standardized_difference_alternative_minus_baseline':standardized['alternative']-standardized['baseline']if w else None,'mean_abs_within_common_cell_distance_gap_pp':sum(c['weight']*abs(c['baseline']['mean_distance_pct']-c['alternative']['mean_distance_pct'])for c in comparable)/w if w else None,'cells':cells}

design=load('m02_distance_control_design.json');outcomes=load('candidate_outcomes.json');meta={(r['symbol'],r['day']):r for r in load('candidate_comparison.json')}
assert all(r['horizon']==1 and r['same_candidate_count']for r in outcomes)
common=[];matched=[];details=[];all_contexts=[];changed_contexts=[];capacity=collections.Counter();original_hashes={}
for name in ('candidate_outcomes.json','candidate_comparison.json','m02_distance_control_design.json'):
 original_hashes[name]=hashlib.sha256((OUT/name).read_bytes()).hexdigest()
for r in outcomes:
 m=meta[(r['symbol'],r['day'])];arms={arm:sorted(r['arms'][arm],key=lambda c:(c['distance_pct'],c['level']))for arm in ('baseline','alternative')}
 assert len(arms['baseline'])==len(arms['alternative'])<=3
 assert all(len({identity(c)for c in cs})==len(cs)for cs in arms.values())
 assert all(c['distance_pct']>=0 and math.isfinite(c['distance_pct'])for cs in arms.values()for c in cs)
 capacity[len(arms['baseline'])]+=1
 shared=set(map(identity,arms['baseline']))&set(map(identity,arms['alternative']))
 changed={arm:[c for c in cs if identity(c)not in shared]for arm,cs in arms.items()}
 def pair(a,b):
  return {'symbol':r['symbol'],'day':r['day'],'baseline':a,'alternative':b,'distance_difference_pp':abs(a['distance_pct']-b['distance_pct']),'distance_difference_ATR':abs(a['level']-b['level'])/m['atr'] if m.get('atr')else None}
 for key in sorted(shared):
  a=next(c for c in arms['baseline']if identity(c)==key);b=next(c for c in arms['alternative']if identity(c)==key)
  assert a['touched']==b['touched']
  common.append(pair(a,b))
 assignments=match(changed['baseline'],changed['alternative'])
 # Counterfactual flip of all outcomes must leave every chosen pairing unchanged.
 flipped={arm:[dict(c,touched=not c['touched'])for c in cs]for arm,cs in changed.items()}
 assert assignments==match(flipped['baseline'],flipped['alternative'])
 for i,j in assignments:matched.append(pair(changed['baseline'][i],changed['alternative'][j]))
 details.append({'symbol':r['symbol'],'day':r['day'],'input':m['path'],'price':m['price'],'atr':m['atr'],'capacity_each_arm':len(arms['baseline']),'shared_exact':len(shared),'changed_each_arm':len(changed['baseline']),'matched_changed':len(assignments),'unmatched_changed_each_arm':len(changed['baseline'])-len(assignments),'changed_candidates':changed})
 all_contexts.append(dict(symbol=r['symbol'],day=r['day'],**arms));changed_contexts.append(dict(symbol=r['symbol'],day=r['day'],**changed))
# Assignment tests: cardinality wins over a greedy nearest pair; caliper is fixed.
a=[dict(distance_pct=0),dict(distance_pct=1)];b=[dict(distance_pct=.8),dict(distance_pct=1.8)]
assert match(a,b)==((0,0),(1,1))
assert match([dict(distance_pct=0)],[dict(distance_pct=1.00001)])==()
raw={arm:{'candidates':sum(len(r[arm])for r in all_contexts),'touched':sum(c['touched']for r in all_contexts for c in r[arm])}for arm in ('baseline','alternative')}
changed_totals={arm:{'candidates':sum(len(r[arm])for r in changed_contexts),'touched':sum(c['touched']for r in changed_contexts for c in r[arm])}for arm in ('baseline','alternative')}
summary={'contexts':len(outcomes),'dates':sorted({r['day']for r in outcomes}),'capacity_context_counts':dict(capacity),'raw':raw,'shared_exact_controls':summary_pairs(common),'changed_candidates':changed_totals,'primary_changed_matched':summary_pairs(matched),'changed_unmatched_each_arm':sum(r['unmatched_changed_each_arm']for r in details),'all_candidates_stratified':strata(all_contexts),'changed_candidates_stratified':strata(changed_contexts),'matching_outcome_blind_checks':len(outcomes),'range_basis':'Point coordinate only (zero width), touch=low<=level<=high of next completed session; no financial range or fill. ATR is fixed within each context, so matching never changes ticker/day volatility.','limitations':['Only two shared decision dates; candidates/tickers/dates are dependent','No later path after a 1-session contact; no 3/5/10/20 comparison supplied','Conditional support can become small after requiring distance comparability; unmatched cases stay visible','Coarse bins can retain different distances and asset distributions; within-context weighting is descriptive, not causal','Matching on distance changes the evaluated subset; no extrapolation to the discarded candidates','No ranking change, financial selection, p-values, calibrated probability, trade return or model judgment inferred']}
result={'design':design,'input_sha256':original_hashes,'summary':summary,'matched_changed_pairs':matched,'shared_exact_pairs':common,'context_audit':details}
for name,h in original_hashes.items():assert hashlib.sha256((OUT/name).read_bytes()).hexdigest()==h
(OUT/'m02_distance_control_results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
compact=dict(summary)
for key in ('all_candidates_stratified','changed_candidates_stratified'):compact[key]={k:v for k,v in compact[key].items()if k!='cells'}
print(json.dumps(compact,ensure_ascii=False,indent=2))
