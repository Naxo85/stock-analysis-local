"""Read-only census of the 18 October natural batch. Writes only this audit folder."""
from __future__ import annotations
import collections, hashlib, json, pathlib, re, statistics, sys
from datetime import datetime, timezone
ROOT = next(p for p in pathlib.Path(__file__).resolve().parents if (p / "src/local_runner").is_dir() and (p / "AGENTS.md").is_file())
OUT = pathlib.Path(__file__).resolve().parent
RUN = ROOT / 'logs/batch/2026-10-18/09-08-40'
OLD = ROOT / 'logs/batch/2026-10-16/15-58-24'
sys.path.insert(0, str(ROOT))
from src.local_runner.adaptive_stage import data_ready
from src.local_runner.technical_archive import validate_archive
from src.local_runner.technical_preparation import option_origins

used = {}
def read(path):
    path = pathlib.Path(path); blob=path.read_bytes()
    used[str(path.relative_to(ROOT)).replace('\\','/')]={'sha256':hashlib.sha256(blob).hexdigest(),'bytes':len(blob)}
    return json.loads(blob)
def dt(v): return datetime.fromisoformat(v.replace('Z','+00:00')) if v else None
def walk(value, path=''):
    if isinstance(value,dict):
        for k,v in value.items():
            yield path+'/'+k,k,v
            yield from walk(v,path+'/'+k)
    elif isinstance(value,list):
        for i,v in enumerate(value):yield from walk(v,path+'/'+str(i))
def finite(v):return isinstance(v,(int,float)) and not isinstance(v,bool)
def count(values):return dict(collections.Counter(map(str,values)))
def stats(values):
    values=sorted(x for x in values if x is not None)
    return {'count':len(values),'sum':round(sum(values),3),'min':round(min(values),3),'median':round(statistics.median(values),3),'max':round(max(values),3)} if values else {}
def cov(c):
    pages=c.get('pages',[]); start=dt(c.get('requested_window',{}).get('start'))
    entirely_before=[p for p in pages if p.get('latest') and start and dt(p['latest'])<start]
    intersect=[p for p in pages if p.get('latest') and start and dt(p['latest'])>=start]
    return {'status':c.get('status'),'terminal_received':c.get('terminal_received'),'has_more':c.get('has_more'),'page_count':c.get('page_count'), 'unique_returned':c.get('returned_count'),'duplicates':c.get('duplicate_count'),'elapsed_seconds':c.get('elapsed_seconds'),'pages_entirely_before_window':len(entirely_before),'seconds_entirely_before_window':round(sum(p.get('elapsed_seconds',0) for p in entirely_before),3),'pages_intersecting_window':len(intersect),'max_page_seconds':max([p.get('elapsed_seconds',0) for p in pages],default=0),'all_terminal':all(p.get('terminal_received') is True for p in pages),'last_has_more':pages[-1].get('has_more') if pages else None,'requested_window':c.get('requested_window'),'scope':c.get('scope')}
summary=read(RUN/'summary.json'); old_summary=read(OLD/'summary.json'); source=read(RUN/'source_update.json')
source_path=ROOT/'logs/source_updates/2026-10-18/09-08-45/summary.json'; sources=read(source_path)
rows=[]; raw_records=[]; archives=[]; anomalies=[]
for symdir in sorted((RUN/'adaptive').iterdir()):
    if not symdir.is_dir() or not (symdir/'input.json').exists():continue
    symbol=symdir.name; data=read(symdir/'input.json'); policy=read(symdir/'policy.json'); wire=read(symdir/'triage.input.json'); tick=read(RUN/'tickers'/f'{symbol}.json'); progress=read(RUN/'source_progress'/f'{symbol}.json')
    s=data['slim']; ph=s.get('price_history',{}); sess=ph.get('sessions',[]); quote=s.get('quote_observation',{})
    invalid=[r for r in sess if not all(finite(r.get(k)) for k in ('open','high','low','close','volume')) or not r['low']<=min(r['open'],r['close'])<=max(r['open'],r['close'])<=r['high'] or r['volume']<0]
    error=None
    try:data_ready(data,policy,dt(data['prepared_at']))
    except Exception as exc:error=type(exc).__name__+': '+str(exc)
    if error:anomalies.append({'symbol':symbol,'kind':'admission_replay_failed','detail':error})
    old=read(OLD/'adaptive'/symbol/'input.json') if (OLD/'adaptive'/symbol/'input.json').exists() else {}
    requested=option_origins(data.get('reference'))
    observations=s.get('levels',{}).get('option_origins',[])
    contract_checks=[]
    for item in observations:
        for exp in item.get('option_details',{}).get('by_expiration',[]):
            contracts=exp.get('observed_contracts',[])
            ois=[x.get('oi') for x in contracts if finite(x.get('oi'))]
            total=sum(ois) if len(ois)==len(contracts) else None
            contract_checks.append({'level':item.get('level'),'expiration':exp.get('expiration'),'status':exp.get('status'),'contract_count':len(contracts),'reported_oi':exp.get('aggregate_oi'),'recomputed_oi':total,'unknown_oi':sum(x.get('oi') is None for x in contracts),'zero_oi':sum(x.get('oi')==0 for x in contracts),'positive_oi_gamma_missing':sum(finite(x.get('oi')) and x['oi']>0 and not finite(x.get('gamma')) for x in contracts),'oi_agrees':total is None or abs(total-(exp.get('aggregate_oi') or 0))<1e-8})
    if any(not x['oi_agrees'] for x in contract_checks):anomalies.append({'symbol':symbol,'kind':'directed_oi_mismatch'})
    paths=[v for p,k,v in walk(s) if k=='path_evidence' and isinstance(v,dict)]
    removed=s.get('measurement_policy',{}).get('removed_auxiliaries',[])
    bad_removed=[p for p,k,v in walk(s) if k in removed]
    archive_keys=[p for p,k,v in walk(wire) if k in {'archive_protocol','archive_id','additional_downloaded_histories','body_text'}]
    row={'symbol':symbol,'prepared_at':data.get('prepared_at'),'slim_at':s.get('as_of'),'routing_revision':data.get('routing_revision'),'data_revision':s.get('data_contract_revision'),'admission_replay_error':error,
      'ownership_present':isinstance(data.get('ownership'),dict),'ownership_matches_input':data.get('ownership',{}).get('owned')==data.get('owned'),'ownership_matches_route':tick.get('route',{}).get('owned')==data.get('owned'),'selection_source':data.get('ownership',{}).get('selection_source'),'ownership_source':data.get('ownership',{}).get('ownership_source'),
      'price_history':{'status':ph.get('status'),'complete':ph.get('window_complete'),'count':len(sess),'last':ph.get('last_session'),'expected_last':ph.get('expected_last_session'),'invalid_rows':len(invalid),'duplicates':len(sess)-len({x.get('date') for x in sess}),'before':old.get('slim',{}).get('price_history',{}).get('last_session'),'before_snapshot':old.get('slim',{}).get('as_of')},
      'quote':quote,'options_capture':s.get('options',{}).get('capture'),'requested_option_origins':requested,'option_origin_statuses':count(x.get('status') for x in observations),'option_origin_checks':contract_checks,
      'measurement_auxiliary_residue':bad_removed,'archive_fields_in_model_input':archive_keys,'path_count':len(paths),'path_statuses':count(x.get('status') for x in paths),'path_pending':sum(x.get('pending_count',0) for x in paths),'path_negative_terminal':sum(x.get('negative_terminal_count',0) for x in paths),'path_positive_excursion_negative_terminal':sum(x.get('positive_excursion_negative_terminal_count',0) for x in paths),'path_intraday_unknown':sum(x.get('intraday_order')=='unknown_with_daily_bars' for x in paths),
      'news':{**cov(data['news'].get('coverage',{})),'items':len(data['news'].get('items',[])),'provider_fetched_at':data['news'].get('provider_fetched_at'),'truncated':data['news'].get('truncated')},'analyst_actions':{**cov(data['analyst_actions'].get('coverage',{})),'actions':len(data['analyst_actions'].get('actions',[])),'provider_fetched_at':data['analyst_actions'].get('provider_fetched_at')},'source_news_seconds':progress.get('news',{}).get('elapsed_seconds'),'source_analyst_seconds':progress.get('analysts',{}).get('elapsed_seconds'),'backfill':None}
    back=symdir/'news_backfill.json'
    if back.exists():
        b=read(back); m=re.search(r'Summary: ([^\r\n]+)',b.get('stdout',''))
        bs=read(m.group(1)) if m else {}
        row['backfill']={'since':b.get('since'),'exit_code':b.get('exit_code'),'summary_file':m.group(1) if m else None,'seconds':sum(x.get('elapsed_seconds',0) for x in bs.get('results',[])),'statuses':[x.get('status') for x in bs.get('results',[])]}
    # Three distinct, timestamped raw acquisitions may exist (general news,
    # analyst parser, and anchor backfill). Scope strictly to this actual run.
    for file in sorted((ROOT/'data/ibkr_news_raw'/symbol).glob('2026-10-18*.json')):
        raw=read(file); at=dt(raw.get('generated_at'))
        if at is None or not dt(summary['started_at'])<=at<=dt(summary['finished_at']):continue
        c=raw.get('coverage',{}); rh=raw.get('raw_headlines',[]); hh=raw.get('headlines',[])
        identities=[(h.get('providerCode'),h.get('articleId')) for h in rh]
        record={'symbol':symbol,'path':str(file.relative_to(ROOT)).replace('\\','/'),'kind':'general' if '.general.' in file.name else 'analysts','generated_at':raw.get('generated_at'),'provider':raw.get('providerCode'),**cov(c),'raw_count':len(rh),'filtered_count':len(hh),'filtered_before_start_count':raw.get('filtered_before_start_count'),'filtered_after_end_count':raw.get('filtered_after_end_count'),'unparseable_timestamp_count':raw.get('unparseable_timestamp_count'),'duplicate_identities_in_final_raw':len(identities)-len(set(identities)),'raw_fingerprint':hashlib.sha256(json.dumps([(h.get('providerCode'),h.get('articleId'),h.get('published_at_raw'),h.get('headline_raw')) for h in rh],separators=(',',':'),ensure_ascii=False).encode()).hexdigest()}
        raw_records.append(record)
    for file in sorted((ROOT/'data/technical_archive'/symbol).glob('*.json')):
        ar=read(file)
        if ar.get('snapshot_at')!=s.get('as_of'):continue
        ae=None
        try:validate_archive(ar)
        except Exception as exc:ae=type(exc).__name__+': '+str(exc)
        ac={'symbol':symbol,'path':str(file.relative_to(ROOT)).replace('\\','/'),'sha256':used[str(file.relative_to(ROOT)).replace('\\','/')]['sha256'],'bytes':file.stat().st_size,'archive_id':ar.get('archive_id'),'snapshot_at':ar.get('snapshot_at'),'source_revision':ar.get('source_revision'),'origin':ar.get('origin'),'validation_error':ae,'daily_rows':len(ar['daily']['rows']),'daily_coverage':ar['daily']['coverage'],'options_coverage':ar['options']['coverage'],'additional_histories_count':len(ar.get('additional_downloaded_histories',[]))}
        archives.append(ac)
    rows.append(row)

per_raw_symbols=collections.defaultdict(list)
for r in raw_records:per_raw_symbols[r['symbol']].append(r)
redownloads=[]
for sym, items in per_raw_symbols.items():
    groups=collections.Counter(r['raw_fingerprint'] for r in items)
    redownloads.append({'symbol':sym,'acquisitions':len(items),'identical_raw_fingerprint_groups':sorted(groups.values(),reverse=True),'pages':sum(r.get('page_count') or 0 for r in items),'acquisition_seconds':round(sum(r.get('elapsed_seconds') or 0 for r in items),3)})
aggregate={
 'scope':{'run':str(RUN.relative_to(ROOT)).replace('\\','/'),'symbols':len(rows),'external_calls':0,'historical_files_modified':False},
 'outcome':{k:summary.get(k) for k in ['duration_seconds','total','success','failed','retained_reports','updated_reports','regenerated_reports','retry_summary']},
 'previous_outcome':{k:old_summary.get(k) for k in ['duration_seconds','total','success','failed','retained_reports','updated_reports','regenerated_reports','retry_summary']},
 'admission_replay_pass':sum(r['admission_replay_error'] is None for r in rows),'routing_revision_counts':count(r['routing_revision'] for r in rows),'data_revision_counts':count(r['data_revision'] for r in rows),
 'ownership_all_consistent':all(r['ownership_present'] and r['ownership_matches_input'] and r['ownership_matches_route'] for r in rows),'ownership_selection_sources':count(r['selection_source'] for r in rows),'ownership_fallback_sources':count(r['ownership_source'] for r in rows),
 'price_history_complete':sum(r['price_history']['complete'] is True for r in rows),'price_history_invalid_rows':sum(r['price_history']['invalid_rows'] for r in rows),'price_history_last_dates':count(r['price_history']['last'] for r in rows),'quote_statuses':count(r['quote'].get('status') for r in rows),
 'archive_count':len(archives),'archive_validation_pass':sum(a['validation_error'] is None for a in archives),'archive_bytes':sum(a['bytes'] for a in archives),'archive_daily_complete':sum(a['daily_coverage'].get('window_complete') is True for a in archives),'archive_options_sampled_complete':sum(a['options_coverage'].get('sampled_capture_complete') is True for a in archives),'model_input_archive_field_hits':sum(len(r['archive_fields_in_model_input']) for r in rows),'removed_auxiliary_hits':sum(len(r['measurement_auxiliary_residue']) for r in rows),
 'option_capture_statuses':count(r['options_capture'].get('status') for r in rows),'directed_option_records':sum(len(r['option_origin_checks']) for r in rows),'directed_oi_mismatches':sum(not x['oi_agrees'] for r in rows for x in r['option_origin_checks']),'directed_positive_oi_without_gamma':sum(x['positive_oi_gamma_missing'] for r in rows for x in r['option_origin_checks']),
 'path_objects':sum(r['path_count'] for r in rows),'path_intraday_unknown':sum(r['path_intraday_unknown'] for r in rows),'path_positive_excursion_negative_terminal_tickers':sum(r['path_positive_excursion_negative_terminal']>0 for r in rows),
 'source_pipeline_seconds':source.get('duration_seconds'),'source_news_seconds':stats([r['source_news_seconds'] for r in rows]),'source_analyst_seconds':stats([r['source_analyst_seconds'] for r in rows]),'backfills':sum(r['backfill'] is not None for r in rows),'backfill_seconds':stats([r['backfill']['seconds'] for r in rows if r['backfill']]),
 'raw_acquisitions':len(raw_records),'raw_kind_counts':count(r['kind'] for r in raw_records),'raw_complete':sum(r['status']=='complete' and r['terminal_received'] is True and r['has_more'] is False and r['all_terminal'] and r['last_has_more'] is False for r in raw_records),'raw_pages':sum(r.get('page_count') or 0 for r in raw_records),'raw_pages_entirely_before_window':sum(r['pages_entirely_before_window'] for r in raw_records),'raw_seconds_entirely_before_window':round(sum(r['seconds_entirely_before_window'] for r in raw_records),3),'raw_acquisition_seconds':stats([r['elapsed_seconds'] for r in raw_records]),'raw_unique_rows_across_acquisitions':sum(r['raw_count'] for r in raw_records),'raw_filtered_rows_across_acquisitions':sum(r['filtered_count'] for r in raw_records),'raw_duplicate_identity_errors':sum(r['duplicate_identities_in_final_raw'] for r in raw_records),'raw_unparseable_timestamp_count':sum(r['unparseable_timestamp_count'] or 0 for r in raw_records),'anomalies':anomalies}
for name,value in [('aggregate.json',aggregate),('per_symbol.json',rows),('raw_acquisitions.json',raw_records),('archives.json',archives),('redownloads.json',redownloads),('evidence_manifest.json',used)]:
    (OUT/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(aggregate,ensure_ascii=False,indent=2))
