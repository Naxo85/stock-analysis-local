"""Offline tests for the effective source clocks and command arguments."""
import subprocess,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace as N
from unittest.mock import patch,Mock
from src.local_runner import run_one,run_batch,adaptive_stage
from src.local_runner import update_ibkr_news_batch as news
from src.local_runner import update_analysis_sources_pipeline as pipeline
from src.local_runner.ibkr_news_pagination import (
 DEFAULT_TOTAL_TIMEOUT,DEFAULT_PAGE_TIMEOUT,DEFAULT_MAX_PAGES,
 DEFAULT_NEWS_PROCESS_TIMEOUT,DEFAULT_NEWS_BACKFILL_TIMEOUT,
)

class SourceDeadlineTests(unittest.TestCase):
    def test_limits_have_bounded_source_only_headroom(self):
        self.assertEqual((DEFAULT_TOTAL_TIMEOUT,DEFAULT_PAGE_TIMEOUT,DEFAULT_MAX_PAGES),(180,30,16))
        self.assertEqual(DEFAULT_NEWS_PROCESS_TIMEOUT,210)
        self.assertEqual(DEFAULT_NEWS_BACKFILL_TIMEOUT,600)
        self.assertGreaterEqual(DEFAULT_NEWS_BACKFILL_TIMEOUT,2*DEFAULT_NEWS_PROCESS_TIMEOUT+120+5)
        self.assertEqual(run_batch.PIPELINE_STAGE_TIMEOUT_SECONDS['prepare'],900)
    def test_cli_defaults_and_explicit_overrides(self):
        for parser in (news._parse_args,pipeline._parse_args):
            with self.subTest(parser=parser.__module__):
                base=['--tickers','NVDA']
                if parser is pipeline._parse_args:base.extend(['--progress-dir','.'])
                args=parser(base)
                self.assertEqual(args.process_timeout,210)
                self.assertEqual(args.timeout,10)
                args=parser(base+['--process-timeout','90','--timeout','7.5'])
                self.assertEqual(args.process_timeout,90)
                self.assertEqual(args.timeout,7.5)
    def test_run_one_effective_command_uses_shared_source_clock(self):
        done=subprocess.CompletedProcess([],0,stdout='',stderr='')
        with patch.object(run_one.subprocess,'run',return_value=done) as run:
            self.assertEqual(run_one._run_preflight_updates(Path('.'),'NVDA'),0)
        commands=[c.args[0] for c in run.call_args_list]
        self.assertEqual(len(commands),2)
        self.assertIn('src.local_runner.update_analyst_ratings_batch',commands[0])
        command=commands[1]
        self.assertEqual(command[command.index('--process-timeout')+1],'210')
        self.assertNotIn('--aggregate-news',command)
    def test_run_batch_effective_command_uses_shared_source_clock(self):
        config=N(update_ibkr_news=True,tickers=['NVDA'])
        with patch.object(run_batch,'_run_non_blocking_prestep',return_value={'status':'ok'}) as run:
            run_batch._run_ibkr_news_update(config)
        command=run.call_args.kwargs['command']
        self.assertEqual(command[command.index('--process-timeout')+1],'210')
    def test_news_subprocess_honors_explicit_override_and_connection_clock(self):
        args=news._parse_args(['--tickers','NVDA','--process-timeout','90','--timeout','7.5'])
        done=subprocess.CompletedProcess([],0,stdout='OK',stderr='')
        with tempfile.TemporaryDirectory() as td,patch.object(news,'run_bounded',return_value=done) as run:
            result=news._run_one(repo_root=Path(td),ticker='NVDA',client_id=1,args=args,log_dir=Path(td))
        self.assertEqual(result['status'],'ok')
        self.assertEqual(run.call_args.kwargs['timeout'],90)
        command=run.call_args.args[0]
        self.assertEqual(command[command.index('--timeout')+1],'7.5')
    def test_pipeline_effective_child_clock_comes_from_same_default(self):
        args=pipeline._parse_args(['--tickers','NVDA','--progress-dir','.']);args.update_news=True;args.update_analysts=False
        done=subprocess.CompletedProcess([],0,stdout='OK',stderr='')
        with tempfile.TemporaryDirectory() as td,patch.object(news,'run_bounded',return_value=done) as run:
            result=pipeline._run_ticker_source_update(repo_root=Path(td),ticker='NVDA',ticker_index=0,
                earnings_context={},args=args,news_log_dir=Path(td),analyst_log_dir=Path(td))
        self.assertEqual(result['status'],'ok');self.assertEqual(run.call_args.kwargs['timeout'],210)
        command=run.call_args.args[0]
        self.assertEqual(command[command.index('--timeout')+1],'10.0')
    def test_process_timeout_preserves_failure_and_partial_output_log(self):
        args=news._parse_args(['--tickers','NVDA'])
        error=subprocess.TimeoutExpired(['fake'],210,output='partial observations',stderr='waiting')
        with tempfile.TemporaryDirectory() as td,patch.object(news,'run_bounded',side_effect=error):
            result=news._run_one(repo_root=Path(td),ticker='NVDA',client_id=1,args=args,log_dir=Path(td))
            self.assertEqual(result['status'],'failed');self.assertEqual(result['error'],'process_timeout_after_210s')
            self.assertIn('partial observations',Path(result['log']).read_text())
            self.assertIn('PROCESS_TIMEOUT',Path(result['log']).read_text())
    def test_adaptive_backfill_actual_call_uses_source_deadline(self):
        class StopAfterInvocation(Exception):pass
        with tempfile.TemporaryDirectory() as td, \
             patch.object(adaptive_stage,'read_json',return_value={}), \
             patch.object(adaptive_stage,'validate_policy',side_effect=lambda p:p), \
             patch.object(adaptive_stage,'load_reference_payload',return_value={'generated_at':'2026-10-13T00:00:00+00:00'}), \
             patch.object(adaptive_stage.one,'_fetch_slim',return_value={}), \
             patch.object(adaptive_stage.one,'_load_analyst_quality',return_value={}), \
             patch.object(adaptive_stage.one,'load_compact_analyst_summary',return_value={}), \
             patch.object(adaptive_stage.one,'load_recent_analyst_actions',return_value={}), \
             patch.object(adaptive_stage.one,'load_recent_news',return_value={}), \
             patch.object(adaptive_stage,'_news_gap',return_value=True), \
             patch.object(adaptive_stage,'run_bounded',side_effect=StopAfterInvocation) as run:
            with self.assertRaises(StopAfterInvocation):
                adaptive_stage.prepare(Path(td),Path(td),'NVDA',False,'normal',policy={'routing_revision':1})
        self.assertEqual(run.call_args.kwargs['timeout'],600)
        self.assertIn('src.local_runner.update_ibkr_news_batch',run.call_args.args[0])
        self.assertIn('--since',run.call_args.args[0])

if __name__=='__main__':unittest.main()
