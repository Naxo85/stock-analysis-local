import json, pathlib, sys
sys.stdout.reconfigure(encoding='utf-8')
ROOT = pathlib.Path(__file__).resolve().parents[3]
def j(p): return json.loads(pathlib.Path(p).read_text(encoding='utf-8-sig'))
mode = sys.argv[1] if len(sys.argv)>1 else 'schema'
base = ROOT/'logs/batch/2026-10-18/09-08-40/adaptive/MP'
if mode=='schema':
    for name in ['input.json','triage.input.json','publish/current_state.json']:
        data=j(base/name)
        print(name, list(data))
        if name=='input.json':
            for key in ['reference','slim','comparison']: print(key, list(data.get(key,{})))
        if name=='publish/current_state.json':
            for key,value in data.items():
                print(key, list(value) if isinstance(value,dict) else str(value)[:100])
elif mode=='print':
    data=j(ROOT/sys.argv[2])
    for key in sys.argv[3:]: data=data[int(key)] if isinstance(data,list) else data[key]
    print(json.dumps(data,ensure_ascii=False,indent=2))
elif mode=='options':
    symbol=sys.argv[2]
    data=j(base.parent/symbol/'input.json')
    for label,slim in [('current', data['slim']), ('reference', data['reference']['slim_snapshot'])]:
        print(label, slim['as_of'], json.dumps(slim['options'],ensure_ascii=False)[:1200])
        print('level keys:',list(slim['levels']))
        for key,rows in slim['levels'].items():
            if not isinstance(rows,list): continue
            for row in rows:
                if isinstance(row,dict) and ('put' in str(row.get('type','')) or 'option_details' in row):
                    print(key,json.dumps({k:v for k,v in row.items() if k not in ('evidence','option_details')},ensure_ascii=False))
                    det=row.get('option_details') or row.get('evidence',{}).get('option_details')
                    if det: print(' details:',json.dumps(det,ensure_ascii=False)[:1800])
elif mode=='cases':
    data=j(pathlib.Path(__file__).parent/'evidence.json')
    for row in data['zones']:
        if row['ticker'] not in sys.argv[2:]:continue
        print(row['batch'],row['ticker'],row['slot'],row['range'],row['components'],row['decision'])
        print('FACTORS',row['factors'])
        if row['batch'].startswith('2026-10-18'):
            print('ASSESSMENT',row['assessment'])
            print('REASON',row['reason'])
            for p in row['puts_within_half_atr_screen_only']:
                print('PUT',p['strike'],p['oi'],p['gamma_share_pct'],round(p['distance_to_zone_atr'],3),[(e['expiration'],e['aggregate_oi']) for e in p['by_expiration']])
elif mode=='compare_puts':
    for sym in sys.argv[2:]:
        data=j(base.parent/sym/'input.json')
        print(sym)
        for label,slim in [('current',data['slim']),('reference',data['reference']['slim_snapshot'])]:
            print(label,slim['as_of'])
            for p in slim['levels'].get('put_walls_top',[]):
                det=p.get('option_details',{})
                print(p['level'],p.get('oi'),p.get('gamma_share_pct'),[(e['expiration'],e['aggregate_oi']) for e in det.get('by_expiration',[])])
        for slot,z in data['reference']['semantic_report']['data']['plan'].items():
            if slot not in ('entry','ambitious_entry') or not z.get('range'): continue
            print(slot,z['range'],z['strength']['components'])
            if z['strength']['components']['opciones']==0:print(z['strength']['factors'])
elif mode=='stats':
    data=j(pathlib.Path(__file__).parent/'evidence.json')
    latest=[r for r in data['zones'] if r['batch'].startswith('2026-10-18')]
    zeros=[r for r in latest if r['components']['opciones']==0]
    print('zeros',len(zeros),'same range',sum(r['previous_components'] is not None for r in zeros),'same zero',sum(r['previous_components'] is not None and r['previous_components']['opciones']==0 for r in zeros))
    exact=[r for r in zeros if any(p['distance_to_zone']==0 for p in r['puts_within_half_atr_screen_only'])]
    print('exact puts with zero',[(r['ticker'],r['slot'],r['total'],r['report_at']) for r in exact])
    print('max-only-option score MP',next(r['total']+25 for r in zeros if r['ticker']=='MP'))
elif mode=='lines':
    needles=sys.argv[3:]
    for i,line in enumerate((ROOT/sys.argv[2]).read_text(encoding='utf-8-sig').splitlines(),1):
        if any(n.lower() in line.lower() for n in needles):print(f'{i}: {line}')
elif mode=='trace':
    data=j(pathlib.Path(__file__).parent/'evidence.json')
    for r in data['zones']:
        if r['ticker'] not in sys.argv[2:] or r['components']['opciones']!=0:continue
        print(r['batch'],r['ticker'],r['slot'],r['range'],r['total'],'same_prior',r['matching_prior_slot'])
        print('exact puts',[(p['strike'],p['oi'],p['gamma_share_pct']) for p in r['puts_within_half_atr_screen_only'] if p['distance_to_zone']==0])
        print('factors',r['factors'])
