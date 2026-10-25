"""Read-only frozen-corpus audit; writes only derived files alongside this script."""
import collections, json, pathlib, sys
sys.stdout.reconfigure(encoding='utf-8')
HERE=pathlib.Path(__file__).resolve().parent
ROOT=HERE.parents[2]
def read(p): return json.loads(p.read_text(encoding='utf-8-sig'))
def plan(d): return d.get('semantic_report',{}).get('data',{}).get('plan',{})
def trim_zone(z):
    return {k:z.get(k) for k in ('range','reason','strength')}
def puts(slim):
    out={}
    for fam in ('put_walls_top','supports','observed_origins'):
        rows=slim.get('levels',{}).get(fam,[])
        if isinstance(rows,dict): rows=rows.get('items',[])
        for x in rows:
            if not isinstance(x,dict): continue
            det=x.get('option_details') or x.get('evidence',{}).get('option_details') or {}
            if 'put' not in x.get('type','') and det.get('option_type')!='put': continue
            strike=det.get('strike',x.get('level'))
            if not isinstance(strike,(int,float)): continue
            item={k:x.get(k) for k in ('type','level','oi','oi_share_pct','gamma_share_pct','gamma_usd_millions','expiration')}
            item.update({'family':fam,'strike':strike,'sampled_expirations':det.get('sampled_expirations'),
                         'by_expiration':[{k:row.get(k) for k in ('expiration','aggregate_oi','gamma_usd_millions','observed_contracts')} for row in det.get('by_expiration',[])]})
            out.setdefault(strike,item)
    return list(out.values())

batches=['2026-10-14/16-07-07','2026-10-15/07-21-28','2026-10-15/12-01-08','2026-10-16/15-58-24','2026-10-18/09-08-40']
allrows=[]; summaries=[]
for batch in batches:
    rows=[]
    for folder in sorted((ROOT/'logs/batch'/batch/'adaptive').iterdir()):
        pp=folder/'publish/current_state.json'
        if not pp.exists(): continue
        pub=read(pp); inp=read(folder/'input.json'); prior=plan(inp.get('reference',{}))
        tri=read(folder/'triage.json') if (folder/'triage.json').exists() else {}
        for key,z in plan(pub).items():
            if key not in ('entry','ambitious_entry') or not z.get('range'): continue
            comps=z['strength']['components']; rng=z['range']
            matched=[(pk,pz) for pk,pz in prior.items() if pk in ('entry','ambitious_entry') and pz.get('range')==rng]
            match=next(((pk,pz) for pk,pz in matched if pk==key),matched[0] if matched else (None,None))
            pc=match[1]['strength']['components'] if match[1] and match[1].get('strength') else None
            atr=inp['slim'].get('technicals',{}).get('atr10')
            option_rows=[]
            for p in puts(inp['slim']):
                distance=max(rng['lower']-p['strike'],0,p['strike']-rng['upper'])
                p={**p,'distance_to_zone':distance,'distance_to_zone_atr':distance/atr if atr else None}
                if p['distance_to_zone_atr'] is not None and p['distance_to_zone_atr']<=0.5: option_rows.append(p)
            row={'batch':batch,'ticker':folder.name,'slot':key,'range':rng,'components':comps,'total':sum(comps.values()),
                 'matching_prior_slot':match[0],'previous_components':pc,'component_deltas':{c:comps[c]-pc[c] for c in comps} if pc else None,
                 'decision':tri.get('decision','full'),'reason':tri.get('reason'),'assessment':tri.get('levels',{}).get('assessment'),
                 'public_reason':z['reason'],'factors':z['strength']['factors'],'report_at':pub['generated_at'],
                 'current_at':inp['slim']['as_of'],'puts_within_half_atr_screen_only':option_rows,
                 'triage_path':str((folder/'triage.json').relative_to(ROOT)),'published_path':str(pp.relative_to(ROOT))}
            rows.append(row)
    same=[r for r in rows if r['previous_components'] is not None]
    summary={'batch':batch,'reports_with_active_zone':len({r['ticker'] for r in rows}),'zones':len(rows),'visible65':sum(r['total']>=65 for r in rows),
             'option_zero':sum(r['components']['opciones']==0 for r in rows),'same_range':len(same),
             'option_increase_same_range':[(r['ticker'],r['slot'],r['component_deltas']['opciones']) for r in same if r['component_deltas']['opciones']>0],
             'option_decrease_same_range':[(r['ticker'],r['slot'],r['component_deltas']['opciones']) for r in same if r['component_deltas']['opciones']<0]}
    summaries.append(summary);allrows.extend(rows)
(HERE/'evidence.json').write_text(json.dumps({'summary':summaries,'zones':allrows},ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(summaries,ensure_ascii=False,indent=2))
print('\nLATEST ZERO SCREEN')
for r in allrows:
    if r['batch']!=batches[-1] or r['components']['opciones']!=0:continue
    print(r['ticker'],r['slot'],r['range'],r['total'],r['decision'],[(p['strike'],p['oi'],p['gamma_share_pct'],round(p['distance_to_zone_atr'],3)) for p in r['puts_within_half_atr_screen_only']])
