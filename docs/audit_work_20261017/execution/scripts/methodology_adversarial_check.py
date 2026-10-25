import json,pathlib,collections,datetime,sys
from zoneinfo import ZoneInfo
ROOT=pathlib.Path.cwd();OUT=ROOT/'.tmp/audit_execution_20261017'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
rows=read(OUT/'candidate_comparison.json');episodes=read(OUT/'zone_episodes.json');zones=read(OUT/'zone_outcomes.json');summary=read(OUT/'local_evaluation_summary.json');option98=read(OUT/'option_panel_inventory.json')
price_changes=[r for r in rows if [c['level'] for c in r['baseline']]!=[c['level']for c in r['alternative']]]
metaonly=[r for r in rows if r['baseline']!=r['alternative'] and [c['level'] for c in r['baseline']]==[c['level'] for c in r['alternative']]]
countdiff=[r for r in rows if len(r['baseline'])!=len(r['alternative'])]
counts=collections.Counter();identities=collections.defaultdict(set); contracts=collections.defaultdict(list); missing=collections.Counter(); invalid=[];feature_future=[];source_dates=[];pub=[];late=[];keys=collections.Counter()
for r in rows:
 p=ROOT/r['path'];review=read(p.parent/'review.json')if(p.parent/'review.json').exists()else{}
 report=p.parent/'publish/output'/r['symbol']/'latest.json'
 if report.exists():
  pub.append({'symbol':r['symbol'],'day':r['day'],'published_at':review.get('published_at'),'status':review.get('status'),'path':r['path']})
  stamp=review.get('reviewed_at')
  if stamp and datetime.datetime.fromisoformat(stamp.replace('Z','+00:00')).astimezone(ZoneInfo('America/New_York')).date().isoformat()>r['day']:
   late.append({'symbol':r['symbol'],'day':r['day'],'reviewed_at':stamp,'status':review.get('status')})
 if r['day']<'2026-10-13':continue
 d=read(p);slim=d['slim'];source_dates.append(r['day'])
 for b in (slim.get('price_history')or{}).get('sessions')or[]:
  if b['date']>=r['day']:feature_future.append({'symbol':r['symbol'],'day':r['day'],'bar':b['date']})
  vals=[b.get(k)for k in ('open','high','low','close')]
  if any(type(v)not in (int,float) or v<=0 for v in vals) or not vals[2]<=min(vals[0],vals[3])<=max(vals[0],vals[3])<=vals[1]:invalid.append({'symbol':r['symbol'],'day':r['day'],'bar':b['date']})
 for kind, candidates in (slim.get('levels')or{}).items():
  if not isinstance(candidates,list):continue
  for c in candidates:
   detail=c.get('option_details')or(c.get('evidence')or{}).get('option_details')
   if not detail:continue
   counts[kind]+=1
   identity=(r['symbol'],detail.get('option_type'),detail.get('strike',c.get('level')))
   identities[identity].add(r['day'])
   for exp in detail.get('by_expiration')or[]:
    for obs in exp.get('observed_contracts')or[]:
     key=identity+(exp.get('expiration'),)
     contracts[key].append({'day':r['day'],'kind':kind,'observation':obs,'aggregate_oi':exp.get('aggregate_oi'),'gamma_usd_millions':exp.get('gamma_usd_millions')})
     for field in ('symbol','root_symbol','contract_size','greeks_updated_at','bid_date','ask_date','trade_date','oi','gamma'):
      if obs.get(field)is None:missing[field]+=1
for z in episodes:keys.update(z['components'])
identitydays=collections.defaultdict(set)
for o in option98:identitydays[(o['symbol'],o['details'].get('option_type'),o['details'].get('strike',o['level']))].add(o['day'])
summary2={'candidate_changes':{'reported_dictionary_changes':summary['candidate_comparison']['same_capacity_inventory_changes'],'actual_price_list_changes':len(price_changes),'metadata_only_changes':len(metaonly),'unequal_capacity_rows':len(countdiff),'metadata_examples':metaonly[:3]},
'publication':{'staged_reports':len(pub),'without_published_at':sum(not p['published_at']for p in pub),'without_published_at_examples':[p for p in pub if not p['published_at']][:10],'review_next_NY_day_count':len(late),'review_next_NY_day_examples':late[:10]},
'episodes':{'rows':len(episodes),'unique_symbol_range':len({(z['symbol'],z['lower'],z['upper'])for z in episodes}),'duplicate_same_day_across_slot':len(episodes)-len({(z['symbol'],z['day'],z['lower'],z['upper'])for z in episodes}),'component_score_sums':dict(keys)},
'features':{'history_inputs':len(source_dates),'future_or_same_day_rows':len(feature_future),'invalid_ohlc':len(invalid)},
'option_panel':{'provided98':len(option98),'provided98_identity_count':len(identitydays),'provided98_identities_multi_dates':sum(len(ds)>1 for ds in identitydays.values()),'all_current_detail_rows':sum(counts.values()),'by_family':dict(counts),'identity_count':len(identities),'identities_multi_dates':sum(len(ds)>1 for ds in identities.values()),'contract_identity_count':len(contracts),'contract_identities_multi_dates':sum(len({x['day']for x in xs})>1 for xs in contracts.values()),'observation_rows_including_family_duplicates':sum(len(x)for x in contracts.values()),'missing_fields_in_observation_rows':dict(missing),'scope':'sampled TOP and admitted origins; presence informative, absence not proof of disappearance'}}
(OUT/'methodology_adversarial_checks.json').write_text(json.dumps(summary2,indent=2),encoding='utf8')
print(json.dumps(summary2,indent=2))
