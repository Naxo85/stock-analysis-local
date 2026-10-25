"""Local, read-only audit study of archived inputs; no network or model calls.

Features are frozen input values. Later archived completed bars are labels only.
Every decision date is included before outcome availability is checked. Revision
and repeated episodes are recorded; this is an exploratory audit, not a trading
backtest or independent temporal confirmation.
"""
import hashlib
import json
import math
import statistics
from collections import Counter, defaultdict
from datetime import datetime, date, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(r'E:/stock-analysis-local')
OUT = ROOT / '.tmp/audit_execution_20261017'
import sys
sys.path.insert(0, str(ROOT))
from gcp_functions.support_resistances_raw.market_sessions import market_session
from datetime import timedelta

def read(p):
    return json.loads(p.read_text(encoding='utf-8-sig'))

def number(v):
    return float(v) if isinstance(v, (int,float)) and not isinstance(v,bool) and math.isfinite(v) else None

def median(xs):
    xs=[x for x in xs if x is not None]
    return statistics.median(xs) if xs else None

def stamp_day(value):
    return datetime.fromisoformat(value.replace('Z','+00:00')).astimezone(ZoneInfo('America/New_York')).date().isoformat()

def ohlc(row):
    vals=tuple(number(row.get(k)) for k in ('open','high','low','close'))
    if any(x is None or x<=0 for x in vals) or not vals[2] <= min(vals[0],vals[3]) <= max(vals[0],vals[3]) <= vals[1]:
        return None
    return vals

items=[]; errors=[]; hashes={}; panel=defaultdict(dict); conflicts=[]
for ix,p in enumerate(sorted((ROOT/'logs/batch').glob('*/*/adaptive/*/input.json'))):
    if ix % 200 == 0: print('READ',ix,flush=True)
    try:
        raw=p.read_bytes(); data=json.loads(raw.decode('utf-8-sig'))
        if not data.get('symbol') or not data.get('prepared_at'): continue
        t0=stamp_day(data['prepared_at']); slim=data.get('slim') or {}
        bars=(slim.get('price_history') or {}).get('sessions') or []
        rel=p.relative_to(ROOT).as_posix(); hashes[rel]=hashlib.sha256(raw).hexdigest()
        item={'path':rel,'symbol':data['symbol'],'prepared_at':data['prepared_at'],
              'day':t0,'revision':data.get('routing_revision'), 'data':data,
              'history_count':len(bars)}
        items.append(item)
        for b in bars:
            day=str(b.get('date',''))[:10]; value=ohlc(b)
            # Only closed-before-capture bars are accepted as label observations.
            if not value or not day or day>=t0: continue
            old=panel[data['symbol']].get(day)
            if old is not None and old['values']!=value:
                old['conflict']=True
                conflicts.append({'symbol':data['symbol'],'date':day,'earlier':old['path'],'later':rel})
            else:
                panel[data['symbol']].setdefault(day,{'values':value,'path':rel,'observed_at':data['prepared_at'],'conflict':False})
    except Exception as e: errors.append({'path':str(p),'error':str(e)})

# One original preparation per ticker/day, last preparation that day, not retries
# or repairs counted as independent decisions. All originals remain inventoried.
perday={}
for item in sorted(items,key=lambda i:i['prepared_at']): perday[(item['symbol'],item['day'])]=item
selected=sorted(perday.values(),key=lambda i:(i['prepared_at'],i['symbol']))

inventory={'input_count':len(items),'ticker_days':len(selected),
 'dates':dict(Counter(i['day'] for i in items)),
 'revisions':dict(Counter(str(i['revision']) for i in items)),
 'with_recent_ohlcv':sum(bool(i['history_count']) for i in items),
 'bars_by_symbol':{s:len(p) for s,p in panel.items()},
 'bar_conflict_count':len(conflicts),'bar_conflicts':conflicts,
 'parse_errors':errors,
 'note':'All input hashes retained; label panel does not become feature evidence.'}
(OUT/'input_inventory.json').write_text(json.dumps(inventory,ensure_ascii=False,indent=2),encoding='utf-8')
(OUT/'original_input_hashes.json').write_text(json.dumps(hashes,indent=2),encoding='utf-8')

# Feature-only examination of candidate breadth and deterministic alternative.
rows=[]; zones=[]; context=[]; timings=[]; episodes=[]; last={}
def item_count(x):
    if isinstance(x,list): return len(x)
    if isinstance(x,dict): return len(x.get('items') or x.get('actions') or [])
    return 0
for item in selected:
    d=item['data']; slim=d.get('slim') or {}; levels=slim.get('levels') or {}
    price=number(slim.get('latest_price')); tech=slim.get('technicals') or {}
    atr=number(tech.get('atr10')); bars=(slim.get('price_history') or {}).get('sessions') or []
    if isinstance(slim.get('latest_price'),dict):price=number(slim['latest_price'].get('price'))
    if price is None: price=number((slim.get('market_state') or {}).get('mid'))
    existing=[]
    for c in levels.get('supports') or []:
        v=number(c.get('level'))
        if v and price and v<=price: existing.append({'level':v,'family':c.get('type') or c.get('kind') or 'support','origin':'supplied_support'})
    recent_pivots=[]
    for k in range(2,len(bars)-2):
        v=number(bars[k].get('low'))
        near=[number(x.get('low')) for x in bars[k-2:k+3]]
        if v and all(x is not None and v<=x for x in near) and price and v<=price:
            recent_pivots.append({'level':v,'family':'confirmed_recent_pivot','origin_date':bars[k]['date'],
                                  'available_date':bars[k+2]['date']})
    # This comparison adds no unobserved AVWAP or full-lookback pivot.
    recent_pivots=sorted(recent_pivots,key=lambda c:c['available_date'],reverse=True)
    pool=existing+recent_pivots
    unique={round(c['level'],6):c for c in pool}
    alt=sorted(unique.values(),key=lambda c:(price-c['level'])/price)[:min(3,len(existing))] if price and existing else []
    baseline=sorted(existing,key=lambda c:(price-c['level'])/price)[:3] if price else []
    rows.append({'symbol':item['symbol'],'day':item['day'],'path':item['path'],
        'price':price,'atr':atr,'existing_lower_count':len(existing),
        'confirmed_recent_pivot_count':len(recent_pivots),
        'new_recent_pivots':sum(all(abs(c['level']-e['level'])>max(.01,abs(c['level'])*1e-6) for e in existing) for c in recent_pivots),
        'baseline':baseline,'alternative':alt,
        'new_under5pct':sum(0 <= (price-c['level'])/price < .05 and all(abs(c['level']-e['level'])>.01 for e in existing) for c in recent_pivots) if price else 0})
    context.append({'symbol':item['symbol'],'day':item['day'],'market_keys':sorted((slim.get('market_state') or {}).keys()),
                    'news_count':item_count(d.get('news')),'analyst_count':item_count(d.get('analyst_actions')),
                    'rs20':number((slim.get('market_state') or {}).get('relative_strength_vs_spy_20d')),
                    'rs60':number((slim.get('market_state') or {}).get('relative_strength_vs_spy_60d'))})
    p=ROOT/item['path']; report=p.parent/'publish/output'/item['symbol']/'latest.json'
    if not report.exists():
        timings.append({'symbol':item['symbol'],'day':item['day'],'published':False})
        continue
    output=read(report); hashes[report.relative_to(ROOT).as_posix()]=hashlib.sha256(report.read_bytes()).hexdigest()
    doc=(output.get('semantic_report') or {}).get('data') or {}
    plan=doc.get('plan') or {}
    review=read(p.parent/'review.json') if (p.parent/'review.json').exists() else {}
    timings.append({'symbol':item['symbol'],'day':item['day'],'published':True,'decision':review.get('decision'),
                    'generated_at':output.get('generated_at'),'prepared_at':item['prepared_at']})
    for slot in ('entry','ambitious_entry'):
        z=plan.get(slot) or {}; bounds=z.get('range'); strength=z.get('strength') or {}
        if not bounds:
            last[(item['symbol'],slot)]=None
            continue
        lo,hi=number(bounds.get('lower')),number(bounds.get('upper'))
        if not lo or not hi or lo>hi: continue
        row={'symbol':item['symbol'],'day':item['day'],'slot':slot,'lower':lo,'upper':hi,
             'components':strength.get('components') or {},'path':item['path'],'report_path':str(report.relative_to(ROOT)),
             'reason':z.get('reason'),'reference_at':output.get('generated_at'),'atr':atr,
             'strength':sum((strength.get('components') or {}).values()),'outcomes':{}}
        future=sorted((day,b) for day,b in panel[item['symbol']].items() if day>item['day'])
        for h in (1,3,5,10,20):
            label={'available':False,'horizon_sessions':h}
            if len(future)>=h and not any(b['conflict'] for _,b in future[:h]):
                seq=future[:h]
                # No gap in expected weekdays may silently shorten the horizon.
                from gcp_functions.support_resistances_raw.market_sessions import market_session
                span=(date.fromisoformat(seq[-1][0])-date.fromisoformat(item['day'])).days
                from datetime import timedelta
                expected=sum(market_session(date.fromisoformat(item['day'])+timedelta(days=j)) for j in range(1,span+1))
                if expected==h:
                    contact=next((k for k,(_,b) in enumerate(seq) if b['values'][2]<=hi and b['values'][1]>=lo),None)
                    label.update(available=True,touched=contact is not None,
                                 bars_entirely_below_zone=sum(b['values'][1]<lo for _,b in seq),
                                 label_end=seq[-1][0])
                    if contact is not None:
                        origin=seq[contact][1]['values'][3];after=seq[contact+1:]
                        label.update(contact_date=seq[contact][0],contact_close=origin,
                                     ambiguous_contact_session=True,post_contact_sessions=len(after))
                        if after:
                            label.update(favorable_excursion_pct=max(0,100*(max(b['values'][1] for _,b in after)/origin-1)),
                                         adverse_excursion_pct=max(0,100*(1-min(b['values'][2] for _,b in after)/origin)),
                                         terminal_return_pct=100*(after[-1][1]['values'][3]/origin-1))
            row['outcomes'][str(h)]=label
        zones.append(row)
        key=(row['symbol'],row['slot']); identity=(row['lower'],row['upper'])
        if last.get(key)!=identity: episodes.append(row)
        last[key]=identity

# Repeated identical zones are retained in the audit record but only the first
# occurrence is used for outcome summaries. Switching away and returning starts
# a new episode; never remove repeats after seeing outcome.
metrics={}
for h in ('1','3','5','10','20'):
    available=[r for r in episodes if r['outcomes'][h]['available']]
    touched=[r for r in available if r['outcomes'][h]['touched']]
    measured=[r for r in touched if 'adverse_excursion_pct' in r['outcomes'][h]]
    metrics[h]={'episodes_with_complete_horizon':len(available),'distinct_start_dates':len({r['day'] for r in available}),
                'touched':len(touched),'post_contact_path_observed':len(measured),
                'median_adverse_excursion_pct':median([r['outcomes'][h]['adverse_excursion_pct'] for r in measured]),
                'median_favorable_excursion_pct':median([r['outcomes'][h]['favorable_excursion_pct'] for r in measured]),
                'median_terminal_return_pct':median([r['outcomes'][h]['terminal_return_pct'] for r in measured])}

result={'inventory':inventory,'candidate_comparison':{'ticker_days':len(rows),
 'with_history':sum(bool(i['history_count']) for i in selected),
 'with_additional_confirmed_recent_pivots':sum(r['new_recent_pivots']>0 for r in rows),
 'with_additional_under5pct':sum(r['new_under5pct']>0 for r in rows),
 'same_capacity_inventory_changes':sum(r['baseline']!=r['alternative'] for r in rows),
 'limitation':'Alternative is an inventory, not financial selection. Available20bars cannot reconstruct omitted126/252-session candidates or every AVWAP anchor.'},
 'zone_rows':len(zones),'zone_episodes':len(episodes),'outcome_metrics':metrics,
 'context_keys':dict(Counter(k for r in context for k in r['market_keys'])),
 'publication':{'ticker_days':len(timings),'published':sum(t['published'] for t in timings)},
 'interpretation':'Exploratory descriptions only; many revisions, shared days and missing horizons prevent validation of new weights, ITV or predictive superiority.'}
for name,value in [('local_evaluation_summary.json',result),('candidate_comparison.json',rows),('zone_outcomes.json',zones),('zone_episodes.json',episodes),('context_inventory.json',context),('review_timing.json',timings),('original_input_hashes.json',hashes)]:
    (OUT/name).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k!='inventory'},ensure_ascii=False,indent=2))
print('INPUTS',len(items),'TICKER_DAYS',len(selected),'HISTORY',inventory['with_recent_ohlcv'],'CONFLICTS',len(conflicts),'ERRORS',len(errors))
