from __future__ import annotations
import hashlib, json, pathlib, sys, collections, ast
from datetime import datetime
ROOT=next(p for p in pathlib.Path(__file__).resolve().parents if (p / "src/local_runner").is_dir() and (p / "AGENTS.md").is_file()); OUT=pathlib.Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from gcp_functions.support_resistances_raw.price_path import horizontal_path_evidence
slim_ast=ast.parse((ROOT/'gcp_functions/support_resistances_slim/main.py').read_text(encoding='utf-8'))
slim_clean_node=next(n for n in slim_ast.body if isinstance(n,ast.FunctionDef) and n.name=='_clean')
slim_clean_namespace={}
exec(compile(ast.Module(body=[slim_clean_node],type_ignores=[]),'<actual-slim-clean>','exec'),slim_clean_namespace)
slim_clean=slim_clean_namespace['_clean']
R=ROOT/'logs/batch/2026-10-18/09-08-40'; OLD=ROOT/'logs/batch/2026-10-16/15-58-24'
def read(p):return json.loads(pathlib.Path(p).read_bytes())
def dt(s):return datetime.fromisoformat(s.replace('Z','+00:00'))
def digest(v):return hashlib.sha256(json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def facts(h):return [h.get('providerCode'),h.get('articleId'),h.get('published_at_raw'),h.get('headline_raw')]
def walk(v,p=''):
    if isinstance(v,dict):
        for k,x in v.items():
            yield p+'/'+k,k,x
            yield from walk(x,p+'/'+k)
    elif isinstance(v,list):
        for i,x in enumerate(v):yield from walk(x,p+'/'+str(i))
raws=read(OUT/'raw_acquisitions.json'); by=collections.defaultdict(list)
for r in raws:by[r['symbol']].append(r)
checks=[]; first_total_pages=0; first_seconds=0; first_rows=0
for symbol,records in by.items():
    records.sort(key=lambda x:x['generated_at'])
    first=read(ROOT/records[0]['path']); base=first['raw_headlines']; first_total_pages+=records[0]['page_count'];first_seconds+=records[0]['elapsed_seconds'];first_rows+=len(base)
    for record in records:
        target=read(ROOT/record['path']); start,end=map(dt,(target['window']['start'],target['window']['end']))
        # Frozen sample equivalence: never relabel the acquisition date in live code.
        derived=[facts(h) for h in base if start<=dt(h['published_at_raw'])<=end]
        expected=[facts(h) for h in target['headlines']]
        checks.append({'symbol':symbol,'source_path':records[0]['path'],'target_path':record['path'],'target_kind':record['kind'],'target_count':len(expected),'derived_count':len(derived),'ordered_identity_text_time_equal':derived==expected,'derived_sha256':digest(derived),'target_sha256':digest(expected),'later_capture_at':record['generated_at'],'first_capture_at':records[0]['generated_at']})
(OUT/'offline_window_equivalence.json').write_text(json.dumps({'scope':'Historical frozen data only; equality of headline identities, exact text and timestamps, not live freshness or downstream parser/consensus state. No network.', 'checks':len(checks),'passed':sum(x['ordered_identity_text_time_equal'] for x in checks),'first_capture_pages':first_total_pages,'all_capture_pages':sum(x['page_count'] for x in raws),'duplicate_capture_pages':sum(x['page_count'] for x in raws)-first_total_pages,'first_capture_seconds':round(first_seconds,3),'all_capture_seconds':round(sum(x['elapsed_seconds'] for x in raws),3),'duplicate_capture_seconds_observed':round(sum(x['elapsed_seconds'] for x in raws)-first_seconds,3),'first_capture_raw_rows':first_rows,'results':checks},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
archives=read(OUT/'archives.json'); replay=[]; badbars=[]; before_after=[]; contracts=[]; source_logs=[]; empties=[]
for a in archives:
    symbol=a['symbol']; ar=read(ROOT/a['path']); d=read(R/'adaptive'/symbol/'input.json'); s=d['slim']; bars=ar['daily']['rows']; old=read(OLD/'adaptive'/symbol/'input.json')
    for p,k,path in walk(s):
        if k!='path_evidence' or not isinstance(path,dict):continue
        calc=horizontal_path_evidence(path.get('coordinate'),bars,path.get('tolerance_abs'),forward_sessions=path.get('forward_sessions',5))
        raw_match=calc==path
        calc=slim_clean(calc)
        mismatched=[k for k in set(calc)|set(path) if calc.get(k)!=path.get(k)]
        replay.append({'symbol':symbol,'path':p,'exact_match':calc==path,'raw_before_slim_clean_exact':raw_match,'mismatched_keys':mismatched,'expected_sha256':digest(path),'recomputed_sha256':digest(calc),'incomplete_data_count':path.get('incomplete_data_count'),'pending_count':path.get('pending_count')})
    if not a['daily_coverage']['window_complete']:
        badbars.append({'symbol':symbol,'invalid_rows':[bars[i] for i in a['daily_coverage']['invalid_row_indexes']],'missing_count':len(a['daily_coverage']['missing_expected_sessions']),'missing_first':a['daily_coverage']['missing_expected_sessions'][:4],'partial_declared':True})
    oldhist=old.get('slim',{}).get('price_history',{}); oh=oldhist.get('sessions',[]); oldlast=oh[-1] if oh else {}
    before_after.append({'symbol':symbol,'old_snapshot':old.get('slim',{}).get('as_of'),'old_last_session':oldhist.get('last_session'),'new_last_session':s['price_history']['last_session'],'old_last_close':oldlast.get('close'),'new_last_close':s['price_history']['sessions'][-1]['close'],'old_last_volume':oldlast.get('volume'),'new_last_volume':s['price_history']['sessions'][-1]['volume'],'old_observation_policy':oldhist.get('observation_policy'),'new_observation_policy':s['price_history'].get('observation_policy')})
    # Record actual quote-quality observations (raw metadata), without classifying
    # the financial usefulness of OI or making claims of complete market coverage.
    found={}
    for p,k,x in walk(s):
        if k=='observed_contracts' and isinstance(x,list):
            for c in x:
                found[(c.get('symbol'),c.get('expiration_date'),c.get('strike'),c.get('option_type'))]=c
    vals=list(found.values());
    contracts.append({'symbol':symbol,'unique_visible_contracts':len(vals),'zero_oi':sum(c.get('oi')==0 for c in vals),'unknown_oi':sum(c.get('oi') is None for c in vals),'zero_bid':sum(c.get('bid')==0 for c in vals),'missing_bid_or_ask':sum(c.get('bid') is None or c.get('ask') is None for c in vals),'crossed_quote':sum(isinstance(c.get('bid'),(int,float)) and isinstance(c.get('ask'),(int,float)) and c['bid']>c['ask'] for c in vals),'missing_quote_timestamp':sum(not c.get('bid_date') or not c.get('ask_date') for c in vals),'multiplier_basis':dict(collections.Counter(c.get('multiplier_basis') for c in vals)),'gamma_unknown_metric_contracts':s['options'].get('gamma_concentration',{}).get('unknown_metric_contracts'),'dealer_sign':s['options'].get('gamma_concentration',{}).get('dealer_position_sign'),'straddle_units':s['options'].get('atm_straddle',{}).get('units'),'straddle_probability':s['options'].get('atm_straddle',{}).get('probability_interpretation')})
    if not d['news']['items']:
        cs=[x for x in raws if x['symbol']==symbol and x['generated_at']==d['news'].get('provider_fetched_at')]
        empties.append({'symbol':symbol,'input_news_count':0,'terminal_complete':d['news']['coverage']['status']=='complete' and d['news']['coverage']['terminal_received'] is True and d['news']['coverage']['has_more'] is False,'returned_count':d['news']['coverage']['returned_count'],'window':d['news']['window'],'matching_raws':cs})
source_path=ROOT/'logs/source_updates/2026-10-18/09-08-45'
for file in source_path.rglob('*.log'):
    text=file.read_text(encoding='utf-8',errors='replace'); hits=[line for line in text.splitlines() if any(x in line.lower() for x in ('timeout','traceback','retry','error','failed'))]
    source_logs.append({'path':str(file.relative_to(ROOT)).replace('\\','/'),'sha256':hashlib.sha256(file.read_bytes()).hexdigest(),'failure_marker_lines':hits})
(OUT/'supplementary_checks.json').write_text(json.dumps({'path_replays':len(replay),'path_replays_exact':sum(x['exact_match'] for x in replay),'path_replay_results':replay,'partial_archives':badbars,'visible_option_contract_quality':contracts,'empty_news_inputs':empties,'before_after_sessions':before_after,'source_logs_checked':len(source_logs),'source_logs_with_failure_markers':[x for x in source_logs if x['failure_marker_lines']],'source_logs':source_logs},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'window_checks':len(checks),'window_equal':sum(x['ordered_identity_text_time_equal'] for x in checks),'first_capture_pages':first_total_pages,'duplicate_capture_pages':sum(x['page_count'] for x in raws)-first_total_pages,'duplicate_capture_seconds_observed':round(sum(x['elapsed_seconds'] for x in raws)-first_seconds,3),'path_replays':len(replay),'path_replays_exact':sum(x['exact_match'] for x in replay),'path_mismatches':[x for x in replay if not x['exact_match']][:3],'source_logs_checked':len(source_logs),'source_logs_with_failure_markers':sum(bool(x['failure_marker_lines']) for x in source_logs)},indent=2))
