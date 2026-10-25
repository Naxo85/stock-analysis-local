"""Offline replay through the real scoped-capture implementation; originals read-only."""
import copy,hashlib,json,sys,tempfile
from datetime import datetime
from pathlib import Path
ROOT=next(p for p in Path(__file__).resolve().parents if (p/'AGENTS.md').is_file() and (p/'src/local_runner').is_dir());sys.path.insert(0,str(ROOT))
from src.local_runner.ibkr_news_capture import get_or_create_capture,derive_probe_payload
from src.local_runner.ibkr_news_update import _compact_payload
from src.local_runner.analyst_ratings import apply_probe_payload,build_empty_ratings_state
OUT=ROOT/'.tmp/news_capture_reuse_recheck'
OUT.mkdir(parents=True,exist_ok=True)
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def dt(x):return datetime.fromisoformat(x.replace('Z','+00:00'))
def h(x):return hashlib.sha256(json.dumps(x,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
checks=read(ROOT/'docs/audit_work_20261017/execution/activation/natural_run_20261018/data/offline_window_equivalence.json')['results']
rows=[];sources={};fetched=[];states_checked=0
with tempfile.TemporaryDirectory(prefix='historical_capture_replay_',dir=OUT) as tmp:
    for check in checks:
        source=read(ROOT/check['source_path']);target=read(ROOT/check['target_path'])
        for rel in (check['source_path'],check['target_path']):sources[rel]=hashlib.sha256((ROOT/rel).read_bytes()).hexdigest()
        def fetch():
            fetched.append(check['symbol']);return copy.deepcopy(source)
        capture=get_or_create_capture(Path(tmp),symbol=source['ticker'],provider=source['providerCode'],contract=source['contract'],connection=source['connection'],fetch=fetch,now=dt(target['generated_at']),max_age_seconds=86400)
        derived=derive_probe_payload(capture,start=dt(target['window']['start']),window_basis=target['window']['basis'],earnings_context=target.get('earnings_context'),now=dt(target['generated_at']),max_age_seconds=86400)
        clock=dt(derived['generated_at']);target_clock=dt(target['generated_at']);earnings=target.get('earnings_context') or {}
        initial=build_empty_ratings_state(symbol=target['ticker'],now=clock,previous_earnings_date=earnings.get('previous_earnings_date'),next_earnings_date=earnings.get('next_earnings_date'))
        states={'empty':initial};stored=ROOT/'data/analyst_ratings'/target['ticker']/'current.json'
        if stored.exists():states['stored_post_run_transform_only']=read(stored);sources[str(stored.relative_to(ROOT))]=hashlib.sha256(stored.read_bytes()).hexdigest()
        comparisons={}
        for name,state in states.items():
            actual=apply_probe_payload(copy.deepcopy(state),derived,now=clock)
            expected=apply_probe_payload(copy.deepcopy(state),target,now=target_clock)
            actual.pop('as_of');expected.pop('as_of');states_checked+=1
            comparisons[name]={'equal_except_as_of':actual==expected,'actual_sha256':h(actual),'expected_sha256':h(expected)}
        actual_compact=_compact_payload(derived);target_compact=_compact_payload(target)
        news_equal=all(actual_compact[k]==target_compact[k] for k in ('status','source','kind','ticker','providerCode','count','items','truncated'))
        rows.append({'ticker':target['ticker'],'source_path':check['source_path'],'target_path':check['target_path'],'kind':check['target_kind'],'serialized_headlines_equal':derived['headlines']==target['headlines'],'news_content_equal':news_equal,'financial_state_comparisons':comparisons,'capture_clock_exact':derived['generated_at']==source['generated_at']==derived['window']['end']==derived['provider_fetched_at'],'coverage_exact_to_first_capture':derived['coverage']==source['coverage'],'raw_exact_to_first_capture':derived['raw_headlines']==source['raw_headlines'],'capture_sha256':capture['capture_sha256'],'view_clock':derived['generated_at'],'original_target_clock':target['generated_at']})
result={'scope':'Historical replay through real get_or_create_capture and derive_probe_payload at original recorded operation times; not live source admission. Actual consumer clocks remain first-capture times, intentionally different from later original acquisitions. Firms/consensus compared excluding only as_of; stored post-run states test the transformation only and are not claimed admissible older-capture overwrites. No network/model/body fetch/original edits. Temporary local capture store removed by context manager.','checks':len(rows),'passed':sum(x['serialized_headlines_equal'] and x['news_content_equal'] and x['capture_clock_exact'] and x['coverage_exact_to_first_capture'] and x['raw_exact_to_first_capture'] and all(c['equal_except_as_of'] for c in x['financial_state_comparisons'].values()) for x in rows),'acquisitions':len(fetched),'unique_symbols':len(set(fetched)),'downstream_comparisons':states_checked,'results':rows,'sources_sha256':sources,'code_sha256':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ['src/local_runner/ibkr_news_capture.py','src/local_runner/ibkr_news_update.py','src/local_runner/analyst_actions.py','src/local_runner/analyst_ratings.py']}}
(OUT/'final_implementation_replay.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k not in ['scope','results','sources_sha256','code_sha256']}))
raise SystemExit(0 if result['passed']==len(rows) and result['acquisitions']==46 else 1)
