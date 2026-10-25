"""Offline contracts for execution-scoped IBKR capture consumers."""
import contextlib
import copy
import io
import json
import subprocess
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace as N
from unittest.mock import patch
from src.local_runner import ibkr_analyst_probe as probe
from src.local_runner import ibkr_analyst_update as analyst
from src.local_runner import ibkr_news_update as news
from src.local_runner import update_ibkr_news_batch as news_batch
from src.local_runner import update_analyst_ratings_batch as analyst_batch
from src.local_runner.ibkr_news_pagination import collect_cached_headlines


class CaptureConsumerTests(unittest.TestCase):
    def setUp(self):
        self.end = datetime.now(timezone.utc) - timedelta(minutes=2)
        self.start = self.end - timedelta(days=2)
        self.contract = N(conId=123, symbol='TEST', exchange='SMART', currency='USD', secType='STK')

    def raw(self, provider='DJ-N'):
        return [N(time=self.end-timedelta(days=d),providerCode=provider,articleId=str(d),
                  headline='Goldman Sachs Raises Test Price Target to $120 From $100, Maintains Buy Rating') for d in (1,3)]

    def collected(self, provider='DJ-N'):
        return collect_cached_headlines(lambda *_:(self.raw(provider),{'terminal_received':True,'has_more':False,'request_id':7}),start=self.start,end=self.end,limit=300)

    def payload(self, provider='DJ-N'):
        values,coverage=self.collected(provider)
        return probe.build_probe_payload(symbol='TEST',contract=self.contract,provider=provider,
            providers=[N(code=provider,name='test')],headlines=values,start=self.start,
            generated_at=self.end,host='127.0.0.1',port=7497,coverage=coverage)

    def fetch_args(self):
        return dict(symbol='TEST',host='127.0.0.1',port=7497,client_id=7,provider='DJ-N',
                    start=self.start,total_results=300,readonly=True,timeout=10,generated_at=self.end)

    def fake_ib(self):
        contract=self.contract
        class FakeIB:
            def connect(self,*a,**kw):pass
            def reqNewsProviders(self):return [N(code='DJ-N',name='Dow Jones'),N(code='BRFUPDN',name='Briefing')]
            def qualifyContracts(self,_):return [contract]
            def isConnected(self):return True
            def disconnect(self):pass
        return FakeIB

    def test_same_scope_derives_two_windows_from_one_acquisition(self):
        with tempfile.TemporaryDirectory() as tmp, patch('ib_insync.IB',self.fake_ib()),patch.object(probe,'_collect_complete_historical_news',return_value=self.collected()) as collect:
            args=self.fetch_args();args.update(capture_dir=Path(tmp),capture_max_age_seconds=86400)
            first=probe.fetch_ibkr_analyst_headlines(**args)
            args.update(start=self.end-timedelta(days=4),generated_at=self.end+timedelta(minutes=1),window_basis='full_anchor')
            second=probe.fetch_ibkr_analyst_headlines(**args)
        self.assertEqual(collect.call_count,1)
        self.assertEqual(first['headline_count'],1);self.assertEqual(second['headline_count'],2)
        self.assertEqual(first['generated_at'],second['generated_at'])
        self.assertEqual(second['window']['end'],self.end.isoformat())
        self.assertEqual(first['coverage'],second['coverage'])
        self.assertEqual(first['raw_headlines'],second['raw_headlines'])
        self.assertEqual(first['capture_ref'],second['capture_ref'])
        self.assertEqual(second['provider_fetched_at'],self.end.isoformat())

    def test_provider_seed_is_separate_and_no_scope_keeps_direct_acquisitions(self):
        with tempfile.TemporaryDirectory() as tmp, patch('ib_insync.IB',self.fake_ib()),patch.object(probe,'_collect_complete_historical_news',side_effect=[self.collected(),self.collected('BRFUPDN'),self.collected(),self.collected()]) as collect:
            args=self.fetch_args();args.update(capture_dir=Path(tmp),capture_max_age_seconds=86400)
            probe.fetch_ibkr_analyst_headlines(**args)
            args['provider']='BRFUPDN';seed=probe.fetch_ibkr_analyst_headlines(**args)
            direct=self.fetch_args();one=probe.fetch_ibkr_analyst_headlines(**direct);two=probe.fetch_ibkr_analyst_headlines(**direct)
        self.assertEqual(collect.call_count,4);self.assertEqual(seed['providerCode'],'BRFUPDN')
        self.assertEqual(one,two);self.assertNotIn('capture_ref',one)

    def test_probe_rejects_partial_capture_configuration_before_connect(self):
        for extra in ({'capture_dir':Path('scope')},{'capture_max_age_seconds':60},{'capture_dir':Path('scope'),'capture_max_age_seconds':float('nan')}):
            with self.subTest(extra=extra),patch('ib_insync.IB') as ib:
                with self.assertRaises(ValueError):probe.fetch_ibkr_analyst_headlines(**self.fetch_args(),**extra)
                ib.assert_not_called()

    def marked_payload(self):
        payload=self.payload()
        payload.update(provider_fetched_at=self.end.isoformat(),capture_ref={'capture_sha256':'hash'},
                       view_window=copy.deepcopy(payload['window']),derived_at=(self.end+timedelta(minutes=1)).isoformat())
        return payload

    def test_news_keeps_capture_clock_provenance_and_operation_filename(self):
        payload=self.marked_payload()
        with tempfile.TemporaryDirectory() as tmp,patch.object(news,'_find_repo_root',return_value=Path(tmp)),patch.object(news,'_window_start',return_value=(self.start,'test')),patch.object(news,'fetch_ibkr_analyst_headlines',return_value=payload) as fetch,contextlib.redirect_stdout(io.StringIO()):
            news.main(['TEST','--capture-dir',tmp+'/scope','--capture-max-age-seconds','86400'])
            current=json.loads((Path(tmp)/'data/ibkr_news_recent/TEST/latest.json').read_text())
            raw=list((Path(tmp)/'data/ibkr_news_raw/TEST').glob('*.json'))
            self.assertEqual(len(raw),1)
            self.assertNotEqual(raw[0].name,news._raw_path(Path(tmp),'TEST','DJ-N',self.end).name)
        self.assertEqual(current['generated_at'],self.end.isoformat());self.assertEqual(current['provider_fetched_at'],self.end.isoformat())
        self.assertEqual(current['capture_ref'],payload['capture_ref']);self.assertEqual(current['coverage'],payload['coverage'])
        self.assertEqual(fetch.call_args.kwargs['capture_dir'],Path(tmp)/'scope')

    def test_analyst_keeps_source_clock_and_source_metadata(self):
        payload=self.marked_payload()
        with tempfile.TemporaryDirectory() as tmp,patch.object(analyst,'_find_repo_root',return_value=Path(tmp)),patch.object(analyst,'_load_earnings_context',return_value={}),patch.object(analyst,'_fetch_provider',return_value=payload) as fetch,contextlib.redirect_stdout(io.StringIO()):
            analyst.main(['TEST','--no-seed','--capture-dir',tmp+'/scope','--capture-max-age-seconds','86400'])
            state=json.loads((Path(tmp)/'data/analyst_ratings/TEST/current.json').read_text())
        self.assertEqual(state['as_of'],self.end.isoformat())
        self.assertEqual(state['last_update']['completed_at'],self.end.isoformat())
        self.assertEqual(state['last_update']['provider_fetched_at'],self.end.isoformat())
        self.assertEqual(state['last_update']['capture_ref'],payload['capture_ref'])
        self.assertEqual(state['last_update']['coverage'],payload['coverage'])
        self.assertEqual(fetch.call_args.kwargs['capture_dir'],Path(tmp)/'scope')

    def test_seed_and_update_keep_providers_separate(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(analyst,'_find_repo_root',return_value=Path(tmp)),patch.object(analyst,'_load_earnings_context',return_value={}),patch.object(analyst,'_fetch_provider',side_effect=[self.payload('BRFUPDN'),self.payload()]) as fetch,contextlib.redirect_stdout(io.StringIO()):
            analyst.main(['TEST','--capture-dir',tmp+'/scope','--capture-max-age-seconds','86400'])
        self.assertEqual([x.kwargs['provider'] for x in fetch.call_args_list],['BRFUPDN','DJ-N'])
        self.assertTrue(all(x.kwargs['capture_dir']==Path(tmp)/'scope' for x in fetch.call_args_list))

    def test_capture_error_preserves_both_last_good_files_exactly(self):
        for module,relative,fetch_name in ((news,'ibkr_news_recent/TEST/latest.json','fetch_ibkr_analyst_headlines'),(analyst,'analyst_ratings/TEST/current.json','_fetch_provider')):
            with self.subTest(module=module.__name__),tempfile.TemporaryDirectory() as tmp:
                path=Path(tmp)/'data'/relative;path.parent.mkdir(parents=True);path.write_text('{"as_of":"2026-10-15T10:00:00+00:00","firms":{}}')
                before=path.read_bytes()
                with patch.object(module,'_find_repo_root',return_value=Path(tmp)),patch.object(module,fetch_name,side_effect=RuntimeError('ibkr_news_capture_invalid')),contextlib.ExitStack() as stack,contextlib.redirect_stdout(io.StringIO()):
                    if module is news:stack.enter_context(patch.object(news,'_window_start',return_value=(self.start,'test')))
                    else:stack.enter_context(patch.object(analyst,'_load_earnings_context',return_value={}))
                    with self.assertRaisesRegex(RuntimeError,'ibkr_news_capture_invalid'):module.main(['TEST','--capture-dir',tmp+'/scope','--capture-max-age-seconds','86400'])
                self.assertEqual(path.read_bytes(),before)
                self.assertFalse((Path(tmp)/'data/ibkr_news_raw').exists())

    def test_older_capture_cannot_regress_existing_analyst_state(self):
        payload=self.marked_payload()
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'data/analyst_ratings/TEST/current.json';path.parent.mkdir(parents=True)
            path.write_text(json.dumps({'as_of':(self.end+timedelta(seconds=1)).isoformat(),'firms':{}}))
            before=path.read_bytes()
            with patch.object(analyst,'_find_repo_root',return_value=Path(tmp)),patch.object(analyst,'_load_earnings_context',return_value={}),patch.object(analyst,'_fetch_provider',return_value=payload):
                with self.assertRaisesRegex(RuntimeError,'older_than_analyst_state'):
                    analyst.main(['TEST','--no-seed','--capture-dir',tmp+'/scope','--capture-max-age-seconds','86400'])
            self.assertEqual(path.read_bytes(),before)
            self.assertFalse((Path(tmp)/'data/ibkr_news_raw').exists())

    def test_analyst_rechecks_state_that_advances_during_acquisition(self):
        payload=self.marked_payload()
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'data/analyst_ratings/TEST/current.json';path.parent.mkdir(parents=True)
            path.write_text(json.dumps({'as_of':(self.end-timedelta(seconds=1)).isoformat(),'firms':{}}))
            newer=json.dumps({'as_of':(self.end+timedelta(seconds=1)).isoformat(),'firms':{}})
            def fetch(**_):path.write_text(newer);return payload
            with patch.object(analyst,'_find_repo_root',return_value=Path(tmp)),patch.object(analyst,'_load_earnings_context',return_value={}),patch.object(analyst,'_fetch_provider',side_effect=fetch):
                with self.assertRaisesRegex(RuntimeError,'older_than_analyst_state'):
                    analyst.main(['TEST','--no-seed','--capture-dir',tmp+'/scope','--capture-max-age-seconds','86400'])
            self.assertEqual(path.read_text(),newer)
            self.assertFalse((Path(tmp)/'data/ibkr_news_raw').exists())

    def test_older_capture_cannot_regress_news_and_same_clock_can_backfill(self):
        payload=self.marked_payload()
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'data/ibkr_news_recent/TEST/latest.json';path.parent.mkdir(parents=True)
            path.write_text(json.dumps({'generated_at':(self.end+timedelta(seconds=1)).isoformat()}))
            before=path.read_bytes()
            with patch.object(news,'_find_repo_root',return_value=Path(tmp)),patch.object(news,'_window_start',return_value=(self.start,'test')),patch.object(news,'fetch_ibkr_analyst_headlines',return_value=payload),contextlib.redirect_stdout(io.StringIO()):
                argv=['TEST','--capture-dir',tmp+'/scope','--capture-max-age-seconds','86400']
                with self.assertRaisesRegex(RuntimeError,'older_than_news_state'):news.main(argv)
                self.assertEqual(path.read_bytes(),before)
                self.assertFalse((Path(tmp)/'data/ibkr_news_raw').exists())
                path.write_text(json.dumps({'generated_at':self.end.isoformat()}))
                news.main(argv);news.main(argv)
                raw=list((Path(tmp)/'data/ibkr_news_raw/TEST').glob('*.general.json'))
                self.assertEqual(len(raw),2)
                self.assertTrue(all(json.loads(p.read_text())['generated_at']==self.end.isoformat() for p in raw))

    def test_cli_requires_paired_positive_explicit_capture_args(self):
        for module,prefix in ((news,['TEST']),(analyst,['TEST']),(news_batch,['--tickers','TEST']),(analyst_batch,['--tickers','TEST'])):
            for suffix in (['--capture-dir','scope'],['--capture-max-age-seconds','60'],['--capture-dir','scope','--capture-max-age-seconds','nan'],['--capture-dir','scope','--capture-max-age-seconds','0']):
                with self.subTest(module=module.__name__,suffix=suffix),contextlib.redirect_stderr(io.StringIO()):
                    with self.assertRaises(SystemExit):module._parse_args(prefix+suffix)

    def test_batch_commands_forward_scope_age_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory=Path(tmp);args=news_batch._parse_args(['--tickers','TEST','--capture-dir',tmp+'/scope','--capture-max-age-seconds','86400'])
            with patch.object(news_batch,'run_bounded',return_value=subprocess.CompletedProcess([],0,'ok','')) as run:
                news_batch._run_one(repo_root=directory,ticker='TEST',client_id=7,args=args,log_dir=directory)
            command=run.call_args.args[0]
            self.assertEqual(command[command.index('--capture-dir')+1],str(directory/'scope'))
            self.assertEqual(command[command.index('--capture-max-age-seconds')+1],'86400.0')
            args=analyst_batch._parse_args(['--tickers','TEST','--capture-dir',tmp+'/scope','--capture-max-age-seconds','86400'])
            with patch.object(analyst_batch.subprocess,'run',return_value=subprocess.CompletedProcess([],0,'ok','')) as run:
                analyst_batch._run_one(repo_root=directory,ticker='TEST',client_id=7,args=args,log_dir=directory,earnings_context={})
            command=run.call_args.args[0]
            self.assertEqual(command[command.index('--capture-dir')+1],str(directory/'scope'))
            self.assertEqual(command[command.index('--capture-max-age-seconds')+1],'86400.0')

if __name__=='__main__':unittest.main()
