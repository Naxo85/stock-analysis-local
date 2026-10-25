"""Offline integration checks for execution-scoped IBKR raw capture reuse.

These tests verify command/lifecycle boundaries, not new market observations.
"""
from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.local_runner import adaptive_stage, run_one
from src.local_runner import update_analysis_sources_pipeline as pipeline
from src.local_runner import update_analyst_ratings_batch as analysts
from src.local_runner import update_ibkr_news_batch as news


class NewsCaptureFlowTests(unittest.TestCase):
    def assert_capture_flags(self, command, scope, age):
        self.assertEqual(command[command.index('--capture-dir') + 1], str(scope))
        self.assertEqual(float(command[command.index('--capture-max-age-seconds') + 1]), age)
        self.assertNotIn('--aggregate-news', command)

    def test_individual_preflight_shares_one_scope_in_existing_order(self):
        with tempfile.TemporaryDirectory() as td:
            scope = Path(td) / 'individual' / 'news_captures'
            done = subprocess.CompletedProcess([], 0, stdout='', stderr='')
            with patch.object(run_one.subprocess, 'run', return_value=done) as run:
                self.assertEqual(run_one._run_preflight_updates(Path(td), 'NVDA',
                    capture_dir=scope, capture_max_age_seconds=1234), 0)
        commands = [call.args[0] for call in run.call_args_list]
        self.assertEqual(len(commands), 2)
        self.assertIn('src.local_runner.update_analyst_ratings_batch', commands[0])
        self.assertIn('src.local_runner.update_ibkr_news_batch', commands[1])
        for command in commands:
            self.assert_capture_flags(command, scope, 1234)

    def test_no_scope_preflight_preserves_old_command_path(self):
        done = subprocess.CompletedProcess([], 0, stdout='', stderr='')
        with patch.object(run_one.subprocess, 'run', return_value=done) as run:
            self.assertEqual(run_one._run_preflight_updates(Path('.'), 'NVDA'), 0)
        for call in run.call_args_list:
            self.assertNotIn('--capture-dir', call.args[0])
            self.assertNotIn('--capture-max-age-seconds', call.args[0])

    def test_news_and_analyst_wrappers_pass_exact_scope_and_age(self):
        done = subprocess.CompletedProcess([], 0, stdout='OK', stderr='')
        with tempfile.TemporaryDirectory() as td:
            path = Path(td)
            scope = path / 'news_captures'
            args = pipeline._parse_args(['--tickers', 'NVDA', '--progress-dir', str(path)])
            args.capture_dir = scope
            args.capture_max_age_seconds = 1234
            with patch.object(news, 'run_bounded', return_value=done) as nr:
                result = news._run_one(repo_root=path, ticker='NVDA', client_id=7201,
                    args=args, log_dir=path)
            self.assertEqual(result['status'], 'ok')
            self.assert_capture_flags(nr.call_args.args[0], scope, 1234)
            with patch.object(analysts.subprocess, 'run', return_value=done) as ar:
                result = analysts._run_one(repo_root=path, ticker='NVDA', client_id=500,
                    args=args, log_dir=path, earnings_context={})
            self.assertEqual(result['status'], 'ok')
            self.assert_capture_flags(ar.call_args.args[0], scope, 1234)

    def test_pipeline_news_retry_keeps_scope_and_original_failure(self):
        events = []
        def news_result(**kwargs):
            events.append(('news', kwargs['client_id'], kwargs['args'].capture_dir))
            return {'status': 'failed', 'error': 'incomplete_capture'} if len(events) == 1 else {'status': 'ok'}
        def analyst_result(**kwargs):
            events.append(('analysts', kwargs['client_id'], kwargs['args'].capture_dir))
            return {'status': 'ok'}
        with tempfile.TemporaryDirectory() as td:
            path = Path(td)
            scope = path / 'news_captures'
            args = pipeline._parse_args(['--tickers', 'NVDA', '--progress-dir', str(path),
                '--update-news', '--update-analysts'])
            args.capture_dir = scope
            args.capture_max_age_seconds = 1234
            with patch.object(pipeline, 'run_news_update', side_effect=news_result), \
                 patch.object(pipeline, 'run_analyst_update', side_effect=analyst_result), \
                 patch.object(pipeline, 'is_gateway_available', return_value=True), \
                 patch.object(pipeline, 'restart_gateway') as restart:
                result = pipeline._run_ticker_source_update(repo_root=path, ticker='NVDA',
                    ticker_index=0, earnings_context={}, args=args, news_log_dir=path,
                    analyst_log_dir=path)
        self.assertEqual(events, [('news', 7201, scope), ('news', 7202, scope), ('analysts', 500, scope)])
        self.assertEqual(result['status'], 'ok')
        self.assertEqual(result['news']['first_error'], 'incomplete_capture')
        self.assertFalse(result['news']['retried_after_gateway_restart'])
        restart.assert_not_called()

    def test_failed_news_does_not_release_analysts_or_success(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td)
            args = pipeline._parse_args(['--tickers', 'NVDA', '--progress-dir', str(path),
                '--update-news', '--update-analysts'])
            with patch.object(pipeline, 'run_news_update', return_value={'status': 'failed', 'error': 'incomplete_capture'}), \
                 patch.object(pipeline, 'run_analyst_update') as analyst, \
                 patch.object(pipeline, 'is_gateway_available', return_value=True):
                result = pipeline._run_ticker_source_update(repo_root=path, ticker='NVDA',
                    ticker_index=0, earnings_context={}, args=args, news_log_dir=path,
                    analyst_log_dir=path)
        self.assertEqual(result['status'], 'failed')
        self.assertIn('incomplete_capture', result['error'])
        analyst.assert_not_called()

    def test_existing_nonblocking_analyst_failure_remains_visible(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td)
            args = pipeline._parse_args(['--tickers', 'NVDA', '--progress-dir', str(path),
                '--update-news', '--update-analysts'])
            with patch.object(pipeline, 'run_news_update', return_value={'status': 'ok'}), \
                 patch.object(pipeline, 'run_analyst_update', return_value={'status': 'failed', 'error': 'analyst_failed'}):
                result = pipeline._run_ticker_source_update(repo_root=path, ticker='NVDA',
                    ticker_index=0, earnings_context={}, args=args, news_log_dir=path,
                    analyst_log_dir=path)
        self.assertEqual(result['status'], 'ok')
        self.assertEqual(result['analysts']['status'], 'failed')
        self.assertEqual(result['analysts']['error'], 'analyst_failed')

    def test_backfill_shares_capture_but_uses_older_full_anchor_window(self):
        class StopAfterCommand(Exception):
            pass
        with tempfile.TemporaryDirectory() as td:
            path = Path(td)
            scope = path / 'news_captures'
            with patch.object(adaptive_stage, 'read_json', return_value={}), \
                 patch.object(adaptive_stage, 'validate_policy', side_effect=lambda p: p), \
                 patch.object(adaptive_stage, 'load_reference_payload', return_value={'generated_at': '2026-10-13T12:00:00+00:00'}), \
                 patch.object(adaptive_stage.one, '_fetch_slim', return_value={}), \
                 patch.object(adaptive_stage.one, '_load_analyst_quality', return_value={}), \
                 patch.object(adaptive_stage.one, 'load_compact_analyst_summary', return_value={}), \
                 patch.object(adaptive_stage.one, 'load_recent_analyst_actions', return_value={}), \
                 patch.object(adaptive_stage.one, 'load_recent_news', return_value={}), \
                 patch.object(adaptive_stage, '_news_gap', return_value=True), \
                 patch.object(adaptive_stage, 'run_bounded', side_effect=StopAfterCommand) as run:
                with self.assertRaises(StopAfterCommand):
                    adaptive_stage.prepare(path, path, 'NVDA', False, 'normal',
                        policy={'routing_revision': 1, 'max_snapshot_age_hours': 2}, capture_dir=scope)
        command = run.call_args.args[0]
        self.assert_capture_flags(command, scope, 7200)
        self.assertEqual(command[command.index('--since') + 1], '2026-10-12T12:00:00+00:00')
        self.assertEqual(run.call_args.kwargs['timeout'], 600)

    def test_admitted_or_completed_preparation_cannot_refresh_capture_or_input(self):
        for marker in ('reservation', 'receipt', 'response', 'review'):
            with self.subTest(marker=marker), tempfile.TemporaryDirectory() as td:
                path = Path(td)
                work = path / 'adaptive' / 'NVDA'
                work.mkdir(parents=True)
                old_input = {'symbol': 'NVDA', 'prepared_at': '2026-10-17T09:00:00+00:00'}
                (work / 'input.json').write_text(json.dumps(old_input), encoding='utf-8')
                (work / 'failure.json').write_text(json.dumps({'error_message': 'stale_source_no_model_call:news'}), encoding='utf-8')
                if marker == 'reservation':
                    (path / 'codex_budget.json').write_text(json.dumps({'calls': {'NVDA:daily': {}}}), encoding='utf-8')
                else:
                    filename = {'receipt': 'daily.receipt.json', 'response': 'daily.response', 'review': 'review.json'}[marker]
                    (work / filename).write_text('{}', encoding='utf-8')
                scope = path / 'news_captures'
                with patch.object(adaptive_stage, 'load_reference_payload') as reference, \
                     patch.object(adaptive_stage, 'run_bounded') as run:
                    adaptive_stage.prepare(path, work, 'NVDA', False, 'normal', capture_dir=scope)
                reference.assert_not_called()
                run.assert_not_called()
                self.assertFalse(scope.exists())
                self.assertFalse((work / 'input_history').exists())
                self.assertEqual(json.loads((work / 'input.json').read_text()), old_input)


    def test_pipeline_derives_separate_scope_per_order_from_progress_parent(self):
        captured = []
        def completed(**kwargs):
            args = kwargs['args']
            captured.append((args.capture_dir, args.capture_max_age_seconds))
            return {'ticker': kwargs['ticker'], 'status': 'ok', 'news': {'status': 'ok'}, 'analysts': {'status': 'skipped'}}
        with tempfile.TemporaryDirectory() as td:
            path = Path(td)
            with patch.object(pipeline, '_find_repo_root', return_value=path), \
                 patch.object(pipeline, 'load_policy', return_value={'max_snapshot_age_hours': 2}), \
                 patch.object(pipeline, '_run_ticker_source_update', side_effect=completed):
                for order in ('first', 'second'):
                    self.assertEqual(pipeline.main(['--tickers', 'NVDA', '--progress-dir',
                        str(path / order / 'source_progress'), '--update-news', '--sleep-seconds', '0']), 0)
        self.assertEqual(captured, [(path / 'first' / 'news_captures', 7200),
                                   (path / 'second' / 'news_captures', 7200)])

    def test_pipeline_scope_override_is_explicit_and_policy_age_is_unchanged(self):
        captured = []
        def completed(**kwargs):
            captured.append((kwargs['args'].capture_dir, kwargs['args'].capture_max_age_seconds))
            return {'ticker': kwargs['ticker'], 'status': 'ok', 'news': {'status': 'ok'}, 'analysts': {'status': 'skipped'}}
        with tempfile.TemporaryDirectory() as td:
            path = Path(td)
            scope = path / 'explicit' / 'news_captures'
            with patch.object(pipeline, '_find_repo_root', return_value=path), \
                 patch.object(pipeline, 'load_policy', return_value={'max_snapshot_age_hours': 2}), \
                 patch.object(pipeline, '_run_ticker_source_update', side_effect=completed):
                self.assertEqual(pipeline.main(['--tickers', 'NVDA', '--progress-dir',
                    str(path / 'source_progress'), '--capture-dir', str(scope),
                    '--update-news', '--sleep-seconds', '0']), 0)
        self.assertEqual(captured, [(scope, 7200)])

    def test_scope_without_freshness_limit_is_rejected_before_subprocess(self):
        with patch.object(run_one.subprocess, 'run') as run:
            with self.assertRaisesRegex(ValueError, 'news_capture_max_age_required'):
                run_one._run_preflight_updates(Path('.'), 'NVDA', capture_dir=Path('scope'))
        run.assert_not_called()

if __name__ == '__main__':
    unittest.main()
