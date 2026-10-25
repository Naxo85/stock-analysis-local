"""Exploratory comparisons from archived features/labels only; no network."""
import json, math, statistics, sys
from pathlib import Path
from collections import Counter, defaultdict
from datetime import date, timedelta, datetime
ROOT=Path(r'E:/stock-analysis-local');OUT=ROOT/'.tmp/audit_execution_20261017';sys.path.insert(0,str(ROOT))
from gcp_functions.support_resistances_raw.market_sessions import market_session
from gcp_functions.support_resistances_raw.price_path import horizontal_path_evidence

def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def med(x):return statistics.median(x) if x else None
def ranks(xs):
    sortedx=sorted(xs); return [(sortedx.index(x)+len(sortedx)-sortedx[::-1].index(x))/2 for x in xs]
def corr(x,y):
    if len(x)<3:return None
    a,b=statistics.mean(x),statistics.mean(y);den=sum((v-a)**2 for v in x)*sum((v-b)**2 for v in y)
    return sum((v-a)*(w-b) for v,w in zip(x,y))/math.sqrt(den) if den else None
def rho(x,y):return corr(ranks(x),ranks(y))

rows=read(OUT/'candidate_comparison.json');zones=read(OUT/'zone_episodes.json');inv=read(OUT/'input_inventory.json')
conflict={(x['symbol'],x['date']) for x in inv['bar_conflicts']};panel=defaultdict(dict);path_desc=[];current=[];option_rows=[]
# Selected feature inputs retain all days, including failed publication. The label
# panel is completed bars only; original conflict registry is conservatively kept.
for ix,r in enumerate(rows):
    if r['day']<'2026-10-13':continue
    if ix%50==0:print('CONTEXT',ix,flush=True)
    d=read(ROOT/r['path']);slim=d['slim'];bars=(slim.get('price_history')or{}).get('sessions')or[]
    for b in bars:
        if b['date']<r['day'] and (r['symbol'],b['date']) not in conflict:panel[r['symbol']][b['date']]=b
    if bars and r['baseline']:
        level=r['baseline'][0]['level'];tol=.2*r['atr'] if r['atr'] else 0
        result=horizontal_path_evidence(level,bars,tol)
        path_desc.append({'symbol':r['symbol'],'day':r['day'],'level':level,'tolerance_is_analysis_only':True,'path':result})
    if r['day']=='2026-10-16':
        news=d.get('news')or{};actions=d.get('analyst_actions')or{};ref=d.get('reference')or{};doc=(ref.get('semantic_report')or{}).get('data')or{}
        current.append({'symbol':r['symbol'],'news_count':len(news.get('items')or[]),'news_generated_at':news.get('generated_at'),'news_status':news.get('status'),'news_truncated':news.get('truncated'),'analyst_count':len(actions.get('actions')or[]),'analyst_as_of':actions.get('as_of'),'research_memory_keys':sorted((d.get('research_memory')or{}).keys()),'catalyst_count':len(doc.get('catalysts')or[]),'next_event':doc.get('next_event'),'market':slim.get('market_state'),'input':r['path']})
    for kind in ('supports','resistances'):
        for c in (slim.get('levels')or{}).get(kind)or[]:
            detail=c.get('option_details')or(c.get('evidence')or{}).get('option_details')
            if detail:option_rows.append({'symbol':r['symbol'],'day':r['day'],'kind':kind,'level':c.get('level'),'details':detail})

# Same count, same input and common date/horizon; no model selection or fills.
comparisons=[]
for r in rows:
    if not r['baseline']:continue
    futures=sorted((d,b) for d,b in panel[r['symbol']].items() if d>r['day'])
    for h in (1,3,5):
        if len(futures)<h:continue
        seq=futures[:h];span=(date.fromisoformat(seq[-1][0])-date.fromisoformat(r['day'])).days
        if sum(market_session(date.fromisoformat(r['day'])+timedelta(days=j)) for j in range(1,span+1))!=h:continue
        if not r['confirmed_recent_pivot_count']:continue
        arms={}
        for arm in ('baseline','alternative'):
            candidates=[]
            for c in r[arm]:
                level=c['level'];touch=next((k for k,(_,b) in enumerate(seq) if b['low']<=level<=b['high']),None)
                after=seq[touch+1:] if touch is not None else []
                close=seq[touch][1]['close'] if touch is not None else None
                candidates.append({'level':level,'distance_pct':100*(r['price']-level)/r['price'],'touched':touch is not None,'contact_date':seq[touch][0]if touch is not None else None,'adverse_pct':max(0,100*(1-min(b['low']for _,b in after)/close))if after else None,'favorable_pct':max(0,100*(max(b['high']for _,b in after)/close-1))if after else None})
            arms[arm]=candidates
        comparisons.append({'symbol':r['symbol'],'day':r['day'],'horizon':h,'arms':arms,'same_candidate_count':len(r['baseline'])==len(r['alternative'])})
cm={}
for h in (1,3,5):
    pairs=[r for r in comparisons if r['horizon']==h];arms={}
    for arm in ('baseline','alternative'):
        cs=[c for r in pairs for c in r['arms'][arm]]
        arms[arm]={'candidates':len(cs),'touched':sum(c['touched']for c in cs),'median_distance_pct':med([c['distance_pct']for c in cs]),'post_contact_measured':sum(c['adverse_pct']is not None for c in cs),'median_adverse_pct':med([c['adverse_pct']for c in cs if c['adverse_pct']is not None])}
    cm[h]={'pairs':len(pairs),'dates':sorted({r['day']for r in pairs}),'arms':arms}

# Ablation = remove a component without reallocating; ordinal stability only.
keys=['estructura','volumen','opciones','confluencia','durabilidad'];ablation={}
for key in keys:
    xs=[z['strength']for z in zones]; ys=[z['strength']-z['components'].get(key,0)for z in zones]
    m={'episodes':len(zones),'rank_correlation_with_original':rho(xs,ys),'threshold70_crossings':sum((a>=70)!=(b>=70)for a,b in zip(xs,ys))}
    for h in ('3','5'):
        zz=[z for z in zones if 'adverse_excursion_pct'in z['outcomes'][h]]
        m[h]={'n':len(zz),'dates':sorted({z['day']for z in zz}),'original_rank_vs_adverse':rho([z['strength']for z in zz],[z['outcomes'][h]['adverse_excursion_pct']for z in zz]),'ablated_rank_vs_adverse':rho([z['strength']-z['components'].get(key,0)for z in zz],[z['outcomes'][h]['adverse_excursion_pct']for z in zz])}
    ablation[key]=m
component_corr={a:{b:corr([z['components'].get(a,0)for z in zones],[z['components'].get(b,0)for z in zones])for b in keys}for a in keys}
allpaths=[e for r in path_desc for e in r['path'].get('events',[])]
path_summary={'coordinate_snapshots':len(path_desc),'mature_events_in_retained_detail':len(allpaths),'adverse_before_favorable':sum(e['extreme_order']=='adverse_extreme_first'for e in allpaths),'same_bar_order_unknown':sum(e['extreme_order']=='same_session_unknown'for e in allpaths),'positive_favorable_and_negative_terminal':sum(e['favorable_excursion_pct']>0 and e['terminal_close_return_pct']<0 for e in allpaths),'not_independent':True}
# Re-read reviews, not provider count inferred from public report generation dates.
reviews=[]
for ix,r in enumerate(rows):
    p=(ROOT/r['path']).parent/'review.json'
    if not p.exists():continue
    rv=read(p);receipts=rv.get('receipts')or[]
    reviews.append({'symbol':r['symbol'],'day':r['day'],'revision':rv.get('routing_revision'),'status':rv.get('status'),'market_data_at':rv.get('market_data_at'),'reviewed_at':rv.get('reviewed_at'),'published_at':rv.get('published_at'),'itv':rv.get('itv'),'calls':len(receipts),'repair':bool((rv.get('luna_repair')or{}).get('attempted')),'tokens':sum((x.get('usage')or{}).get('total_tokens',0)for x in receipts)})
review_summary={'ticker_days':len(reviews),'status':dict(Counter(r['status']for r in reviews)),'calls':sum(r['calls']for r in reviews),'repair_ticker_days':sum(r['repair']for r in reviews),'tokens':sum(r['tokens']for r in reviews),'materiality_labels_available':False}
result={'candidate_matched_capacity':cm,'ablation':ablation,'component_correlations':component_corr,'path_description':path_summary,'reviews':review_summary,'events_context':{'current_inputs':len(current),'with_news':sum(r['news_count']>0 for r in current),'with_analyst_actions':sum(r['analyst_count']>0 for r in current),'with_next_event':sum(bool(r['next_event'])for r in current),'sector_returns_series':0,'market_full_series':0,'expectations_point_in_time_structured':0},'option_rows':len(option_rows),'limits':'Exploratory, chosen alternatives visible before outcomes; no independent holdout, confidence/pvalues, executable returns, optimized weights or predictive adoption.'}
for name,obj in [('comparison_extensions.json',result),('candidate_outcomes.json',comparisons),('historical_path_examples.json',path_desc),('event_context_inventory.json',current),('review_cadence.json',reviews),('option_panel_inventory.json',option_rows)]:
    (OUT/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False,indent=2),flush=True)
