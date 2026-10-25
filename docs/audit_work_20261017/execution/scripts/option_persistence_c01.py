"""Conditional historical observations, no inference from TOP absence or dealer flow."""
import json, pathlib, collections, math, statistics, hashlib
from datetime import datetime, date, timedelta, timezone
ROOT=pathlib.Path.cwd(); OUT=ROOT/'.tmp/audit_execution_20261017'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def finite(v):return type(v)in(int,float)and math.isfinite(v)
def median(v):return statistics.median(v)if v else None
def dt(v):return datetime.fromisoformat(v.replace('Z','+00:00'))
def stamp(v):
 try:return datetime.fromtimestamp(float(v)/1000,timezone.utc)
 except (ValueError,TypeError,OverflowError,OSError):return None
rows=read(OUT/'candidate_comparison.json');groups=collections.defaultdict(list);input_hashes={};input_count=0;family_counts=collections.Counter();detail_rows=0
for r in rows:
 if r['day']<'2026-10-13':continue
 p=ROOT/r['path'];content=p.read_bytes();d=json.loads(content.decode('utf-8-sig'));slim=d['slim'];input_count+=1;input_hashes[r['path']]=hashlib.sha256(content).hexdigest()
 for kind,candidates in (slim.get('levels')or{}).items():
  if not isinstance(candidates,list):continue
  for c in candidates:
   detail=c.get('option_details')or(c.get('evidence')or{}).get('option_details')
   if not detail:continue
   detail_rows+=1;family_counts[kind]+=1
   for expiry in detail.get('by_expiration')or[]:
    key=(r['symbol'],r['day'],detail.get('option_type'),detail.get('strike',c.get('level')),expiry.get('expiration'))
    # Different contract order does not fabricate a conflict, while every value is retained.
    value=dict(expiry,observed_contracts=sorted(expiry.get('observed_contracts')or[],key=lambda x:json.dumps(x,sort_keys=True)))
    groups[key].append({'family':kind,'value':value,'as_of':slim.get('as_of'),'input':r['path']})

valid=[];conflicts=[];duplicate_count=0;field_counts=collections.Counter();quote_counts=collections.Counter();quote_ages=[];unknown_dates=0;future_dates=0
for key, copies in groups.items():
 variants={json.dumps(x['value'],sort_keys=True,separators=(',',':'))for x in copies}
 if len(variants)!=1:
  conflicts.append({'identity_day':list(key),'copies':copies});continue
 duplicate_count+=len(copies)-1
 value=copies[0]['value'];contracts=value.get('observed_contracts')or[]
 wall_oi=value.get('aggregate_oi')
 oi=sum(c['oi']for c in contracts)if contracts and all(finite(c.get('oi'))and c['oi']>=0 for c in contracts)else None
 status=value.get('status');observed=status=='observed' and bool(contracts)
 oi_state='not_observed_in_sample' if not observed else 'unknown' if not finite(oi) else 'zero' if oi==0 else 'positive' if oi>0 else 'invalid'
 field_counts[oi_state]+=1
 obs={'symbol':key[0],'day':key[1],'side':key[2],'strike':key[3],'expiration':key[4],
      'as_of':copies[0]['as_of'],'source_input':copies[0]['input'],'families':sorted({x['family']for x in copies}),
      'status':status,'observed_contract_count':len(contracts),'observed_contract_oi':oi,'wall_gamma_eligible_oi':wall_oi,'oi_state':oi_state,
      'gamma_usd_millions':value.get('gamma_usd_millions'),'observed_contracts':contracts}
 valid.append(obs)
 for c in contracts:
  bid,ask=c.get('bid'),c.get('ask')
  quality='missing_or_nonfinite' if not finite(bid)or not finite(ask)else 'negative' if min(bid,ask)<0 else 'crossed' if bid>ask else 'zero_bid_or_ask' if min(bid,ask)==0 else 'positive_ordered_two_sided'
  quote_counts[quality]+=1
  times=[stamp(c.get('bid_date')),stamp(c.get('ask_date'))]
  if all(times):
   age=(dt(obs['as_of'])-min(times)).total_seconds();quote_ages.append(age)
   future_dates+=(max(times)-dt(obs['as_of'])).total_seconds() > 5
  else:unknown_dates+=1

by_identity=collections.defaultdict(list)
for v in valid:by_identity[(v['symbol'],v['side'],v['strike'],v['expiration'])].append(v)
pairs=[];changes=collections.Counter();missing_pairs=0
for key,observations in by_identity.items():
 observations=sorted(observations,key=lambda v:v['as_of'])
 for a,b in zip(observations,observations[1:]):
  if a['day']==b['day']:raise AssertionError('not deduplicated')
  observed=a['oi_state']in('zero','positive')and b['oi_state']in('zero','positive')
  pair={'identity':list(key),'first_day':a['day'],'last_day':b['day'],'first_oi_state':a['oi_state'],'last_oi_state':b['oi_state'],
        'oi_comparable':observed,'first_oi':a['observed_contract_oi'],'last_oi':b['observed_contract_oi']}
  if observed:
   delta=b['observed_contract_oi']-a['observed_contract_oi'];pair['delta_oi']=delta
   pair['delta_oi_pct']=100*delta/a['observed_contract_oi']if a['observed_contract_oi'] else None
   changes['increased'if delta>0 else 'decreased'if delta<0 else 'unchanged']+=1
  else:missing_pairs+=1
  pairs.append(pair)
summary={'input_count':input_count,'dates':sorted({v['day']for v in valid}),'detail_rows_before_expansion':detail_rows,'families':dict(family_counts),
 'expiry_family_rows':sum(len(v)for v in groups.values()),'unique_identity_day_groups':len(groups),'conflicting_groups_excluded':len(conflicts),'exact_duplicate_family_rows_removed':duplicate_count,
 'retained_identity_day_observations':len(valid),'pseudo_contract_identities':len(by_identity),'identities_observed_on_multiple_dates':sum(len(v)>1 for v in by_identity.values()),
 'oi_states':dict(field_counts),'wall_zero_with_positive_observed_oi':sum(v['wall_gamma_eligible_oi']==0 and v['oi_state']=='positive'for v in valid),'consecutive_observation_pairs':len(pairs),'oi_comparable_pairs':sum(changes.values()),'incomparable_observation_pairs':missing_pairs,'oi_pair_changes':dict(changes),
 'quote_quality_observed_contracts':dict(quote_counts),'dated_bid_ask_pairs':len(quote_ages),'unknown_bid_ask_dates':unknown_dates,'future_by_more_than_5_seconds':future_dates,
 'median_quote_age_seconds':median(quote_ages),'quote_ages_gt_1h':sum(x>3600 for x in quote_ages),'quote_ages_gt_1d':sum(x>86400 for x in quote_ages),
 'limits':['4 capture dates; conditional on appearing in sampled TOP/admitted levels','Pseudo identity lacks OCC symbol/root/deliverable/multiplier: cannot guarantee exact economic contract identity across corporate actions','Historical parser discarded contracts with missing gamma; not_observed is not a market disappearance','Observed-contract OI is summed from stored contracts independently of wall gamma eligibility; wall aggregate is retained separately. Neither covers contracts excluded by the old parser or unrequested expirations','Recorded zero OI can include provider missing values coerced to zero by the historical parser; no provider-true-zero inference is possible from this archive alone','OI effective date unknown; changes are differences between observed snapshots, not trades or signed flows','Dealer inventory, trade aggressor side, continuous chain, intraday path, IV surface and expiry time not observed','Quote timestamps and ordered book do not prove liquidity, fill or simultaneous underlying/Greek observation']}
(OUT/'option_persistence_c01.json').write_text(json.dumps({'summary':summary,'observations':valid,'pairs':pairs,'conflicts':conflicts,'input_sha256':input_hashes},indent=2),encoding='utf8')
print(json.dumps(summary,indent=2))
