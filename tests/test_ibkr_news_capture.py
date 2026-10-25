"""Offline scope/identity/EOF/immutability tests: no provider or model calls."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
from threading import Event
from types import SimpleNamespace as N
import unittest
from unittest.mock import Mock, patch
from src.local_runner.ibkr_analyst_probe import build_probe_payload
from src.local_runner.ibkr_news_pagination import collect_cached_headlines
from src.local_runner.ibkr_news_capture import CaptureError, _write_immutable, derive_probe_payload, get_or_create_capture

END = datetime(2026,10,18,9,0,0,123456,tzinfo=timezone.utc)
NOW, START, MAX_AGE = END+timedelta(minutes=5), END-timedelta(days=5), 86400
CONTRACT = dict(conId=123,symbol='X',exchange='SMART',currency='USD',secType='STK')
CONNECTION = dict(host='127.0.0.1',port=7497)

def make_payload(provider='DJ-N',contract=None,connection=None,empty=False):
    contract,connection=contract or CONTRACT,connection or CONNECTION
    def row(id,time): return N(time=time,providerCode=provider,articleId=id,headline='Company raises guidance '+id)
    later,recent,exact,boundary,old=(row('later',END+timedelta(microseconds=1)),row('recent',END-timedelta(days=1)),row('exact',START),row('boundary',END-timedelta(days=7)),row('old',END-timedelta(days=20)))
    pages=iter([([],False)] if empty else [([later,recent,exact,boundary],True),([boundary,old],False)])
    def fetch(cursor,limit,timeout):
        values,more=next(pages)
        return values,dict(terminal_received=True,has_more=more,request_id=17)
    raw,coverage=collect_cached_headlines(fetch,start=START,end=END,limit=4)
    return build_probe_payload(symbol='X',contract=N(**contract),provider=provider,providers=[],headlines=raw,start=START,generated_at=END,coverage=coverage,**connection)

class CaptureTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.scope=Path(self.temp.name)/'preparation'
    def acquire(self,fetch=None,**overrides):
        args=dict(symbol='X',provider='DJ-N',contract=CONTRACT,connection=CONNECTION,fetch=fetch or Mock(return_value=make_payload()),now=NOW,max_age_seconds=MAX_AGE)
        args.update(overrides)
        return get_or_create_capture(self.scope,**args)
    def derive(self,capture,**overrides):
        args=dict(start=START,window_basis='current',now=NOW,max_age_seconds=MAX_AGE);args.update(overrides)
        return derive_probe_payload(capture,**args)
    def test_one_acquisition_serves_older_anchor_without_relabeling(self):
        source=make_payload();fetch=Mock(return_value=source);capture=self.acquire(fetch)
        self.assertEqual(self.acquire(fetch,now=NOW+timedelta(minutes=10)),capture)
        self.assertEqual(fetch.call_count,1)
        current=self.derive(capture)
        older=self.derive(capture,start=END-timedelta(days=30),window_basis='anchor',now=NOW+timedelta(minutes=10),earnings_context={'dated':True})
        self.assertEqual([r['articleId'] for r in current['headlines']],['recent','exact'])
        self.assertEqual([r['articleId'] for r in older['headlines']],['recent','exact','boundary','old'])
        for view in (current,older):
            self.assertEqual(view['generated_at'],source['generated_at'])
            self.assertEqual(view['provider_fetched_at'],source['generated_at'])
            self.assertEqual(view['window']['end'],source['window']['end'])
            self.assertEqual(view['coverage'],source['coverage'])
            self.assertEqual(view['raw_headlines'],source['raw_headlines'])
            self.assertEqual(view['filtered_after_end_count'],1)
        self.assertNotEqual(older['window']['start'],older['coverage']['requested_window']['start'])
        self.assertEqual(older['view_window'],older['window'])
        self.assertEqual(older['capture_ref']['capture_sha256'],capture['capture_sha256'])
        self.assertEqual(older['earnings_context'],{'dated':True})
    def test_derived_and_caller_mutation_cannot_change_capture(self):
        source=make_payload();capture=self.acquire(Mock(return_value=source));before=deepcopy(capture)
        view=self.derive(capture);view['headlines'][0]['triage']['status']='changed';view['raw_headlines'].clear();view['coverage']['pages'].clear();source['raw_headlines'].clear()
        self.assertEqual(capture,before)
        self.assertNotEqual(self.derive(capture)['headlines'][0]['triage']['status'],'changed')
        capture['payload']['raw_headlines'].clear()
        self.assertEqual(self.acquire(),before)
    def test_empty_cache_and_empty_view_preserve_real_eof(self):
        capture=self.acquire(Mock(return_value=make_payload(empty=True)))
        view=self.derive(capture,start=END-timedelta(days=100))
        self.assertEqual(view['headlines'],[]);self.assertEqual(view['raw_headline_count'],0)
        self.assertIs(view['coverage']['has_more'],False)
        self.scope=self.scope.parent/'nonempty'
        view=self.derive(self.acquire(),start=END-timedelta(hours=1))
        self.assertEqual(view['headlines'],[]);self.assertEqual(view['raw_headline_count'],5)
        self.assertEqual(view['filtered_before_start_count'],4)
    def test_provider_contract_connection_and_execution_are_separate(self):
        first=self.acquire()
        provider=self.acquire(Mock(return_value=make_payload(provider='BRFUPDN')),provider='BRFUPDN')
        contract=dict(CONTRACT,conId=456)
        other_contract=self.acquire(Mock(return_value=make_payload(contract=contract)),contract=contract)
        connection=dict(CONNECTION,port=4002)
        other_connection=self.acquire(Mock(return_value=make_payload(connection=connection)),connection=connection)
        self.scope=self.scope.parent/'next-preparation';scope=self.acquire()
        self.assertEqual(len({c['capture_sha256'] for c in (first,provider,other_contract,other_connection,scope)}),5)
    def test_copy_to_other_scope_fails_without_fetch(self):
        self.acquire();copied=self.scope.parent/'copied';shutil.copytree(self.scope,copied);self.scope=copied
        fetch=Mock()
        with self.assertRaisesRegex(CaptureError,'index_mismatch'):self.acquire(fetch)
        fetch.assert_not_called()
    def test_stale_existing_capture_never_refreshes(self):
        self.acquire();paths=list(self.scope.rglob('*.json'));before={str(p):p.read_bytes() for p in paths};fetch=Mock()
        with self.assertRaisesRegex(CaptureError,'stale'):self.acquire(fetch,now=END+timedelta(seconds=MAX_AGE,microseconds=1))
        fetch.assert_not_called();self.assertEqual({str(p):p.read_bytes() for p in paths},before)
        self.acquire(fetch,now=END+timedelta(seconds=MAX_AGE));fetch.assert_not_called()
    def test_invalid_clock_or_age_fails_before_fetch(self):
        for field,value in [('max_age_seconds',0),('max_age_seconds',float('inf')),('max_age_seconds',float('nan')),('max_age_seconds',True),('now',NOW.replace(tzinfo=None))]:
            with self.subTest(field=field,value=value):
                fetch=Mock()
                with self.assertRaises(CaptureError):self.acquire(fetch,**{field:value})
                fetch.assert_not_called()
        self.assertFalse(self.scope.exists())
    def test_future_capture_writes_no_successful_index(self):
        with self.assertRaisesRegex(CaptureError,'future_capture'):self.acquire(now=END-timedelta(microseconds=1))
        self.assertEqual(list(self.scope.rglob('*.json')),[])
    def test_derived_bad_window_or_time_fails(self):
        capture=self.acquire()
        for args in [{'start':END+timedelta(microseconds=1)},{'start':START.replace(tzinfo=None)},{'now':END-timedelta(microseconds=1)},{'now':END+timedelta(days=2)}]:
            with self.subTest(args=args),self.assertRaises(CaptureError):self.derive(capture,**args)
    def test_payload_identity_mismatch_never_persists(self):
        for change in [{'providerCode':'BRFUPDN'},{'ticker':'Y'},{'contract':dict(CONTRACT,conId=999)},{'connection':dict(CONNECTION,port=4002)}]:
            with self.subTest(change=change):
                payload=make_payload();payload.update(change)
                with self.assertRaisesRegex(CaptureError,'identity_mismatch'):self.acquire(Mock(return_value=payload))
                self.assertEqual(list(self.scope.rglob('*.json')),[])
    def test_legacy_generic_complete_partial_and_error_rejected(self):
        mutations=[lambda p:p.update(coverage={'status':'complete','terminal_received':True,'has_more':False}),lambda p:p['coverage'].update(method='other'),lambda p:p['coverage'].update(scope='requested_window_only'),lambda p:p['coverage'].update(pagination_complete=False),lambda p:p['coverage'].update(terminal_received=False),lambda p:p['coverage'].update(has_more=True),lambda p:p['coverage'].update(status='error'),lambda p:p.update(error='request timeout'),lambda p:p['coverage'].update(errors=['timeout']),lambda p:p.update(truncated=True)]
        for i,mutate in enumerate(mutations):
            with self.subTest(mutation=i):
                payload=make_payload();mutate(payload)
                with self.assertRaises(CaptureError):self.acquire(Mock(return_value=payload))
                self.assertEqual(list(self.scope.rglob('*.json')),[])
    def test_inconsistent_raw_eof_and_query_proof_rejected(self):
        mutations=[lambda p:p.update(generated_at=(END+timedelta(seconds=1)).isoformat()),lambda p:p['coverage']['requested_window'].update(start=(START-timedelta(days=1)).isoformat()),lambda p:p.update(raw_headline_count=999),lambda p:p['raw_headlines'].reverse(),lambda p:p['raw_headlines'][0].update(articleId='old'),lambda p:p['raw_headlines'][0].update(conId=999),lambda p:p['raw_headlines'][0].update(published_at_raw='unknown'),lambda p:p['raw_headlines'][0].update(published_at_raw=(END+timedelta(seconds=1)).isoformat()),lambda p:p.update(headlines=[]),lambda p:p['coverage']['pages'][-1].update(has_more=True),lambda p:p['coverage']['pages'][0].update(has_more=False),lambda p:p['coverage']['pages'][1].update(cursor_exclusive=END.isoformat()),lambda p:p['coverage']['pages'][0].update(duplicate_count=1),lambda p:p['coverage'].update(page_count=1),lambda p:p['coverage'].update(duplicate_count=0),lambda p:p['coverage']['pages'][0].update(earliest=END.isoformat())]
        for i,mutate in enumerate(mutations):
            with self.subTest(mutation=i):
                payload=make_payload();mutate(payload)
                with self.assertRaises(CaptureError):self.acquire(Mock(return_value=payload))
                self.assertEqual(list(self.scope.rglob('*.json')),[])
    def test_saved_digest_tamper_never_reacquires(self):
        capture=self.acquire();path=self.scope/'objects'/(capture['capture_sha256']+'.json')
        stored=json.loads(path.read_text(encoding='utf-8'));stored['payload']['raw_headlines'][0]['headline_raw']='changed';path.write_text(json.dumps(stored),encoding='utf-8');fetch=Mock()
        with self.assertRaisesRegex(CaptureError,'digest_mismatch'):self.acquire(fetch)
        fetch.assert_not_called()
    def test_corrupt_missing_and_traversal_references_fail(self):
        capture=self.acquire();index=next((self.scope/'keys').glob('*.json'));original=index.read_text(encoding='utf-8');fetch=Mock()
        for value in ['not json',json.dumps(dict(json.loads(original),capture_sha256='../../outside')),json.dumps(dict(json.loads(original),capture_sha256='0'*64))]:
            with self.subTest(value=value):
                index.write_text(value,encoding='utf-8')
                with self.assertRaises(CaptureError):self.acquire(fetch)
        fetch.assert_not_called();index.write_text(original,encoding='utf-8');(self.scope/'objects'/(capture['capture_sha256']+'.json')).unlink()
        with self.assertRaisesRegex(CaptureError,'unreadable'):self.acquire(fetch)
        fetch.assert_not_called()
    def test_fetch_failure_has_no_authority_explicit_retry_can_succeed(self):
        with self.assertRaisesRegex(RuntimeError,'provider failed'):self.acquire(Mock(side_effect=RuntimeError('provider failed')))
        self.assertEqual(list(self.scope.rglob('*.json')),[]);self.assertEqual(list(self.scope.rglob('*.lock')),[])
        self.assertEqual(self.acquire()['payload']['raw_headline_count'],5)
    def test_immutable_write_never_replaces_existing_bytes(self):
        target=self.scope/'object.json';_write_immutable(target,{'value':'first'});before=target.read_bytes();_write_immutable(target,{'value':'first'})
        with self.assertRaisesRegex(CaptureError,'immutable_conflict'):_write_immutable(target,{'value':'second'})
        self.assertEqual(target.read_bytes(),before);self.assertEqual(list(self.scope.glob('*.tmp')),[])
    def test_failed_atomic_write_leaves_no_final_or_index(self):
        with patch('src.local_runner.ibkr_news_capture.os.link',side_effect=OSError('disk failure')):
            with self.assertRaisesRegex(OSError,'disk failure'):self.acquire()
        self.assertEqual(list(self.scope.rglob('*.json')),[]);self.assertEqual(list(self.scope.rglob('*.tmp')),[])
    def test_concurrent_consumers_only_fetch_once(self):
        started,release,second_started=Event(),Event(),Event()
        def fetch():
            started.set();self.assertTrue(release.wait(5));return make_payload()
        acquisition=Mock(side_effect=fetch)
        def second():second_started.set();return self.acquire(acquisition)
        with ThreadPoolExecutor(max_workers=2) as pool:
            first=pool.submit(self.acquire,acquisition);self.assertTrue(started.wait(5));concurrent=pool.submit(second);self.assertTrue(second_started.wait(5));release.set();self.assertEqual(first.result(timeout=10),concurrent.result(timeout=10))
        self.assertEqual(acquisition.call_count,1)
    def test_identical_duplicates_inside_first_page_remain_valid(self):
        item=N(time=END-timedelta(days=1),providerCode='DJ-N',articleId='same',headline='Identical')
        raw,coverage=collect_cached_headlines(lambda *args:([item,item],dict(terminal_received=True,has_more=False,request_id=17)),start=START,end=END,limit=4)
        payload=build_probe_payload(symbol='X',contract=N(**CONTRACT),provider='DJ-N',providers=[],headlines=raw,start=START,generated_at=END,coverage=coverage,**CONNECTION)
        capture=self.acquire(Mock(return_value=payload))
        self.assertEqual(capture['payload']['coverage']['pages'][0]['duplicate_count'],1)
        self.assertEqual(self.derive(capture)['headline_count'],1)
    def test_actual_natural_capture_preserves_original_bytes(self):
        directory=next((p for p in Path(__file__).resolve().parents if (p/'src'/'local_runner').is_dir()),None)
        path=directory/'data'/'ibkr_news_raw'/'NVDA'/'2026-10-18T09-34-18Z.DJ-N.general.json' if directory else Path('missing')
        if not path.exists():self.skipTest('optional immutable natural-run artifact absent')
        original=path.read_bytes();payload=json.loads(original);generated=datetime.fromisoformat(payload['generated_at'])
        capture=self.acquire(Mock(return_value=payload),symbol='NVDA',contract=payload['contract'],connection=payload['connection'],now=generated+timedelta(minutes=5))
        start=generated-timedelta(days=30);view=self.derive(capture,start=start,now=generated+timedelta(minutes=10))
        expected=[r for r in payload['raw_headlines'] if start<=datetime.fromisoformat(r['published_at_raw'])<=generated]
        self.assertEqual(view['headlines'],expected);self.assertEqual(view['raw_headline_count'],4065);self.assertEqual(view['coverage']['page_count'],14)
        self.assertEqual(hashlib.sha256(path.read_bytes()).digest(),hashlib.sha256(original).digest())

if __name__=='__main__':unittest.main()
